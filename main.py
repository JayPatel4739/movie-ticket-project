from flask import Flask, render_template, request, jsonify, session
from pymongo import MongoClient
from bson import ObjectId
from bson.errors import InvalidId
from flask_cors import CORS
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'movie-ticket-secret-key-2024')
CORS(app)

MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://mongo:27017/moviedb')
client = MongoClient(MONGO_URI)
db = client.get_database()
movies_collection = db.movies
bookings_collection = db.bookings
offers_collection = db.offers
users_collection = db.users

DEFAULT_OFFERS = [
    {'name': 'Buy 3 Get 1 Free', 'code': None, 'type': 'bulk', 'buy_seats': 3, 'get_seats': 1, 'active': True},
    {'name': '20% Off', 'code': 'SAVE20', 'type': 'coupon', 'discount_percent': 20, 'active': True},
    {'name': '10% Off', 'code': 'SAVE10', 'type': 'coupon', 'discount_percent': 10, 'active': True},
    {'name': '30% Off', 'code': 'SAVE30', 'type': 'coupon', 'discount_percent': 30, 'active': True},
]

for offer in DEFAULT_OFFERS:
    if not offers_collection.find_one({'code': offer['code']}) if offer['code'] else not offers_collection.find_one({'name': offer['name']}):
        offers_collection.insert_one(offer)

if not users_collection.find_one({'username': 'admin'}):
    users_collection.insert_one({'username': 'admin', 'password': 'admin123', 'role': 'admin'})


def get_bulk_discount(seats):
    offer = offers_collection.find_one({'type': 'bulk', 'active': True})
    if not offer:
        return 0
    buy_seats = offer.get('buy_seats', 3)
    get_seats = offer.get('get_seats', 1)
    cycles = seats // buy_seats
    return cycles * get_seats


def get_coupon_discount(code, total_seats):
    offer = offers_collection.find_one({'code': code.upper(), 'type': 'coupon', 'active': True})
    if not offer:
        return 0
    discount_percent = offer.get('discount_percent', 0)
    return (discount_percent / 100) * total_seats


def serialize_doc(doc):
    if doc and '_id' in doc:
        doc['id'] = str(doc['_id'])
        del doc['_id']
    if doc and 'movie_id' in doc and isinstance(doc.get('movie_id'), ObjectId):
        doc['movie_id'] = str(doc['movie_id'])
    return doc


def generate_booking_id():
    today = datetime.now().strftime('%Y%m%d')
    count = bookings_collection.count_documents({}) + 1
    return f"BK-{today}-{count:03d}"


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/book')
def booking_page():
    return render_template('booking.html')


@app.route('/api/movies', methods=['GET'])
def get_movies():
    search = request.args.get('search', '')
    booking_date = request.args.get('date', '')
    query = {}
    if search:
        query['name'] = {'$regex': search, '$options': 'i'}
    movies = list(movies_collection.find(query))
    result = []
    for m in movies:
        doc = serialize_doc(m)
        total_seats = doc.get('total_seats', 0)

        if booking_date:
            timings = doc.get('timings', [])
            for timing in timings:
                booked = 0
                existing = bookings_collection.find({
                    'movie_id': ObjectId(doc['id']),
                    'booking_date': booking_date,
                    'timing': timing
                })
                for b in existing:
                    booked += b.get('seats_booked', 0)
                doc[f'available_{timing.replace(" ", "_").replace(":", "")}'] = total_seats - booked
        result.append(doc)
    return jsonify(result)


@app.route('/api/movies', methods=['POST'])
def add_movie():
    data = request.get_json()
    name = data.get('name', '').strip()
    genre = data.get('genre', '').strip()
    timings = data.get('timings', [])

    if not name:
        return jsonify({'error': 'Movie name cannot be empty'}), 400

    try:
        total_seats = int(data.get('total_seats', 0))
        if total_seats <= 0:
            return jsonify({'error': 'total_seats must be greater than 0'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'total_seats must be a valid integer'}), 400

    rows = data.get('rows', 10)
    seats_per_row = data.get('seats_per_row', 20)

    price_per_seat = data.get('price_per_seat')
    if price_per_seat is not None:
        try:
            price_per_seat = int(price_per_seat)
            if price_per_seat <= 0:
                return jsonify({'error': 'price_per_seat must be greater than 0'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'price_per_seat must be a valid integer'}), 400

    if isinstance(timings, str):
        timings = [t.strip() for t in timings.split(',') if t.strip()]
    elif not isinstance(timings, list):
        timings = []

    movie = {
        'name': name,
        'genre': genre,
        'timings': timings,
        'total_seats': total_seats,
        'rows': rows,
        'seats_per_row': seats_per_row,
        'price_per_seat': price_per_seat
    }
    result = movies_collection.insert_one(movie)
    movie['id'] = str(result.inserted_id)
    del movie['_id']
    return jsonify(movie), 201


@app.route('/api/movies/<movie_id>/availability', methods=['GET'])
def get_movie_availability(movie_id):
    date = request.args.get('date', '')

    try:
        oid = ObjectId(movie_id)
    except InvalidId:
        return jsonify({'error': 'Invalid movie ID'}), 404

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    total_seats = movie.get('total_seats', 0)
    timings = movie.get('timings', [])

    availability = {}
    for timing in timings:
        booked = 0
        existing = bookings_collection.find({
            'movie_id': oid,
            'booking_date': date,
            'timing': timing
        })
        for b in existing:
            booked += b.get('seats_booked', 0)
        availability[timing] = total_seats - booked

    return jsonify({
        'movie_id': str(oid),
        'date': date,
        'total_seats': total_seats,
        'availability': availability
    })


@app.route('/api/movies/<movie_id>/seats', methods=['GET'])
def get_booked_seats(movie_id):
    date = request.args.get('date', '')
    timing = request.args.get('timing', '')

    try:
        oid = ObjectId(movie_id)
    except InvalidId:
        return jsonify({'error': 'Invalid movie ID'}), 404

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    query = {'movie_id': oid, 'booking_date': date}
    if timing:
        query['timing'] = timing

    bookings = list(bookings_collection.find(query))
    booked_seats = []
    for b in bookings:
        seats = b.get('seats', [])
        booked_seats.extend(seats)

    return jsonify({
        'movie_id': str(oid),
        'date': date,
        'timing': timing,
        'booked_seats': booked_seats
    })


@app.route('/api/movies/<movie_id>', methods=['GET'])
def get_movie(movie_id):
    try:
        oid = ObjectId(movie_id)
    except InvalidId:
        return jsonify({'error': 'Invalid movie ID'}), 404

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    return jsonify(serialize_doc(movie))


@app.route('/api/movies/<movie_id>', methods=['PUT'])
def update_movie(movie_id):
    try:
        oid = ObjectId(movie_id)
    except InvalidId:
        return jsonify({'error': 'Invalid movie ID'}), 404

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Movie name is required'}), 400

    genre = data.get('genre', '').strip()
    timings = data.get('timings', [])
    rows = data.get('rows', 10)
    seats_per_row = data.get('seats_per_row', 10)
    total_seats = data.get('total_seats', rows * seats_per_row)
    price_per_seat = data.get('price_per_seat')

    update_data = {
        'name': name,
        'genre': genre,
        'timings': timings,
        'rows': rows,
        'seats_per_row': seats_per_row,
        'total_seats': total_seats,
    }
    if price_per_seat is not None:
        update_data['price_per_seat'] = price_per_seat

    movies_collection.update_one({'_id': oid}, {'$set': update_data})
    updated_movie = movies_collection.find_one({'_id': oid})
    return jsonify(serialize_doc(updated_movie))


@app.route('/api/movies/<movie_id>', methods=['DELETE'])
def delete_movie(movie_id):
    try:
        oid = ObjectId(movie_id)
    except InvalidId:
        return jsonify({'error': 'Invalid movie ID'}), 404

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    movies_collection.delete_one({'_id': oid})
    bookings_collection.delete_many({'movie_id': oid})
    return jsonify({'message': 'Movie deleted successfully'})


@app.route('/api/book', methods=['POST'])
def book_ticket():
    data = request.get_json()
    movie_id = data.get('movie_id')
    contact_number = data.get('contact_number', '').strip()
    coupon_code = data.get('coupon_code', '').strip()
    booking_date = data.get('booking_date', '').strip()
    selected_timing = data.get('timing', '').strip()
    selected_seats = data.get('seats', [])

    if not contact_number:
        return jsonify({'error': 'Contact number cannot be empty'}), 400
    if not booking_date:
        return jsonify({'error': 'Booking date is required'}), 400
    if not selected_seats or len(selected_seats) == 0:
        return jsonify({'error': 'Please select at least one seat'}), 400

    seats_to_book = len(selected_seats)

    try:
        oid = ObjectId(movie_id)
    except (InvalidId, TypeError):
        return jsonify({'error': 'Invalid movie ID'}), 400

    movie = movies_collection.find_one({'_id': oid})
    if not movie:
        return jsonify({'error': 'Movie not found'}), 404

    for seat in selected_seats:
        existing = bookings_collection.find_one({
            'movie_id': oid,
            'booking_date': booking_date,
            'timing': selected_timing,
            'seats': seat
        })
        if existing:
            return jsonify({'error': f'Seat {seat} is already booked'}), 400

    total_seats = movie.get('total_seats', 0)
    booked_seats = 0
    existing_bookings = bookings_collection.find({
        'movie_id': oid,
        'booking_date': booking_date,
        'timing': selected_timing
    })
    for b in existing_bookings:
        booked_seats += len(b.get('seats', []))

    available_seats = total_seats - booked_seats
    if available_seats < seats_to_book:
        return jsonify({'error': f'Not enough seats for this show. Only {available_seats} seats available'}), 400

    price_per_seat = movie.get('price_per_seat') or 0
    bulk_discount = get_bulk_discount(seats_to_book)
    coupon_discount_seats = get_coupon_discount(coupon_code, seats_to_book) if coupon_code else 0

    base_seats = seats_to_book
    price_after_bulk = base_seats * price_per_seat
    bulk_discount_value = bulk_discount * price_per_seat
    price_after_bulk -= bulk_discount_value

    coupon_discount_value = (coupon_discount_seats / seats_to_book) * price_after_bulk if price_after_bulk > 0 else 0
    total_price = max(price_after_bulk - coupon_discount_value, price_per_seat)

    booking = {
        'booking_id': generate_booking_id(),
        'movie_id': oid,
        'movie_name': movie['name'],
        'contact_number': contact_number,
        'booking_date': booking_date,
        'timing': selected_timing,
        'seats': selected_seats,
        'price_per_seat': price_per_seat,
        'bulk_discount_seats': bulk_discount,
        'coupon_code': coupon_code.upper() if coupon_code else None,
        'coupon_discount_seats': coupon_discount_seats,
        'total_price': total_price,
        'bulk_savings': bulk_discount_value,
        'coupon_savings': coupon_discount_value,
        'timestamp': datetime.now().isoformat()
    }
    bookings_collection.insert_one(booking)

    return jsonify({
        'booking_id': booking['booking_id'],
        'seats_booked': base_seats,
        'total_price': total_price,
        'bulk_savings': bulk_discount_value,
        'coupon_savings': coupon_discount_value,
        'coupon_code': booking['coupon_code'],
        'success': True
    })


@app.route('/api/cancel', methods=['POST'])
def cancel_ticket():
    data = request.get_json()
    booking_id = data.get('booking_id', '').strip()

    if not booking_id:
        return jsonify({'error': 'booking_id is required'}), 400

    booking = bookings_collection.find_one({'booking_id': booking_id})
    if not booking:
        return jsonify({'error': 'Booking not found'}), 404

    bookings_collection.delete_one({'booking_id': booking_id})

    return jsonify({
        'success': True
    })


@app.route('/api/bookings/search', methods=['GET'])
def search_bookings_by_phone():
    phone = request.args.get('phone', '').strip()
    if not phone:
        return jsonify({'error': 'Phone number is required'}), 400

    today = datetime.now().strftime('%Y-%m-%d')
    bookings = list(bookings_collection.find({
        'contact_number': phone,
        'booking_date': {'$gte': today}
    }))
    result = []
    for b in bookings:
        b['id'] = str(b['_id'])
        del b['_id']
        if isinstance(b.get('movie_id'), ObjectId):
            b['movie_id'] = str(b['movie_id'])
        result.append(b)
    return jsonify(result)


@app.route('/cancel', methods=['GET'])
def cancel_page():
    return render_template('cancel.html')


@app.route('/api/bookings', methods=['GET'])
def get_bookings():
    bookings = list(bookings_collection.find())
    result = []
    for b in bookings:
        b['id'] = str(b['_id'])
        del b['_id']
        if isinstance(b.get('movie_id'), ObjectId):
            b['movie_id'] = str(b['movie_id'])
        result.append(b)
    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)


@app.route('/api/offers', methods=['GET'])
def get_offers():
    offers = list(offers_collection.find())
    return jsonify([serialize_doc(o) for o in offers])


@app.route('/api/offers', methods=['POST'])
def add_offer():
    data = request.get_json()
    offer_type = data.get('type', 'bulk')
    name = data.get('name', '').strip()
    code = data.get('code', '').strip() or None

    if not name:
        return jsonify({'error': 'Offer name is required'}), 400

    offer = {'name': name, 'code': code, 'type': offer_type, 'active': data.get('active', True)}

    if offer_type == 'bulk':
        buy_seats = data.get('buy_seats', 0)
        get_seats = data.get('get_seats', 0)
        if buy_seats <= 0:
            return jsonify({'error': 'buy_seats must be greater than 0'}), 400
        if get_seats < 0:
            return jsonify({'error': 'get_seats cannot be negative'}), 400
        offer['buy_seats'] = buy_seats
        offer['get_seats'] = get_seats
    elif offer_type == 'coupon':
        if not code:
            return jsonify({'error': 'Coupon code is required for coupon type'}), 400
        discount_percent = data.get('discount_percent', 0)
        if discount_percent <= 0 or discount_percent > 100:
            return jsonify({'error': 'discount_percent must be between 1 and 100'}), 400
        offer['discount_percent'] = discount_percent

    result = offers_collection.insert_one(offer)
    offer['id'] = str(result.inserted_id)
    del offer['_id']
    return jsonify(offer), 201


@app.route('/api/offers/<offer_id>', methods=['PUT'])
def update_offer(offer_id):
    try:
        oid = ObjectId(offer_id)
    except InvalidId:
        return jsonify({'error': 'Invalid offer ID'}), 404

    offer = offers_collection.find_one({'_id': oid})
    if not offer:
        return jsonify({'error': 'Offer not found'}), 404

    data = request.get_json()
    update_fields = {}
    if 'name' in data:
        update_fields['name'] = data['name'].strip()
    if 'code' in data:
        update_fields['code'] = data['code'].strip() or None
    if 'buy_seats' in data:
        update_fields['buy_seats'] = data['buy_seats']
    if 'get_seats' in data:
        update_fields['get_seats'] = data['get_seats']
    if 'discount_percent' in data:
        update_fields['discount_percent'] = data['discount_percent']
    if 'active' in data:
        update_fields['active'] = data['active']

    offers_collection.update_one({'_id': oid}, {'$set': update_fields})
    updated = offers_collection.find_one({'_id': oid})
    return jsonify(serialize_doc(updated))


@app.route('/api/offers/<offer_id>', methods=['DELETE'])
def delete_offer(offer_id):
    try:
        oid = ObjectId(offer_id)
    except InvalidId:
        return jsonify({'error': 'Invalid offer ID'}), 404

    result = offers_collection.delete_one({'_id': oid})
    if result.deleted_count == 0:
        return jsonify({'error': 'Offer not found'}), 404
    return jsonify({'message': 'Offer deleted successfully'})


@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')


@app.route('/admin', methods=['GET'])
def admin_page():
    if not session.get('admin_logged_in'):
        return render_template('login.html', error='Please login first')
    return render_template('admin.html')


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = users_collection.find_one({'username': username, 'password': password})
    if user:
        session['admin_logged_in'] = True
        session['admin_username'] = username
        return jsonify({'success': True, 'message': 'Login successful'})

    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})


@app.route('/api/admin/check', methods=['GET'])
def check_admin():
    if session.get('admin_logged_in'):
        return jsonify({'logged_in': True, 'username': session.get('admin_username')})
    return jsonify({'logged_in': False})