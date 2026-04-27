import pytest
from main import app
from bson import ObjectId
import mongomock

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def mock_db(monkeypatch):
    mock_client = mongomock.MongoClient()
    mock_db = mock_client['moviedb']
    monkeypatch.setattr('main.client', mock_client)
    monkeypatch.setattr('main.db', mock_db)
    monkeypatch.setattr('main.movies_collection', mock_db.movies)
    monkeypatch.setattr('main.bookings_collection', mock_db.bookings)
    monkeypatch.setattr('main.offers_collection', mock_db.offers)
    return mock_db

def test_add_movie_valid(client, mock_db):
    response = client.post('/api/movies', json={
        'name': 'Inception',
        'genre': 'Sci-Fi',
        'timings': ['2:00 PM', '5:00 PM', '9:00 PM'],
        'total_seats': 100,
        'rows': 10,
        'seats_per_row': 20,
        'price_per_seat': 150
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Inception'
    assert data['total_seats'] == 100
    assert data['rows'] == 10
    assert data['seats_per_row'] == 20
    assert data['price_per_seat'] == 150

def test_add_movie_invalid(client, mock_db):
    response = client.post('/api/movies', json={
        'name': '',
        'total_seats': 100
    })
    assert response.status_code == 400
    assert 'error' in response.get_json()

def test_book_ticket(client, mock_db):
    movie = mock_db.movies.insert_one({
        'name': 'Test Movie',
        'genre': 'Action',
        'timings': ['9:00 PM'],
        'total_seats': 50,
        'price_per_seat': 100
    })

    response = client.post('/api/book', json={
        'movie_id': str(movie.inserted_id),
        'contact_number': '1234567890',
        'booking_date': '2026-04-23',
        'timing': '9:00 PM',
        'seats': ['A1', 'A2']
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
    assert data['seats_booked'] == 2

def test_overbook_prevention(client, mock_db):
    movie = mock_db.movies.insert_one({
        'name': 'Full Movie',
        'genre': 'Drama',
        'timings': ['8:00 PM'],
        'total_seats': 2,
        'price_per_seat': 100
    })

    response = client.post('/api/book', json={
        'movie_id': str(movie.inserted_id),
        'contact_number': '1234567890',
        'booking_date': '2026-04-23',
        'timing': '8:00 PM',
        'seats': []
    })
    assert response.status_code == 400
    assert 'select at least one seat' in response.get_json()['error']

def test_cancel_ticket(client, mock_db):
    movie = mock_db.movies.insert_one({
        'name': 'Cancel Test',
        'genre': 'Comedy',
        'timings': ['6:00 PM'],
        'total_seats': 20,
        'available_seats': 18
    })

    booking = mock_db.bookings.insert_one({
        'booking_id': 'BK-20240101-001',
        'movie_id': movie.inserted_id,
        'movie_name': 'Cancel Test',
        'contact_number': '1234567890',
        'seats_booked': 2,
        'booking_date': '2026-04-23',
        'timing': '6:00 PM',
        'timestamp': '2024-01-01T12:00:00'
    })

    response = client.post('/api/cancel', json={
        'booking_id': 'BK-20240101-001'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

def test_search_movie(client, mock_db):
    mock_db.movies.insert_many([
        {'name': 'Avengers', 'genre': 'Action', 'timings': ['5:00 PM'], 'total_seats': 100, 'available_seats': 100},
        {'name': 'Avatar', 'genre': 'Sci-Fi', 'timings': ['7:00 PM'], 'total_seats': 150, 'available_seats': 150},
        {'name': 'Batman', 'genre': 'Action', 'timings': ['9:00 PM'], 'total_seats': 80, 'available_seats': 80}
    ])

    response = client.get('/api/movies?search=Avengers')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['name'] == 'Avengers'

def test_movie_not_found(client, mock_db):
    fake_id = str(ObjectId())
    response = client.get(f'/api/movies/{fake_id}')
    assert response.status_code == 404

def test_cancel_invalid_id(client, mock_db):
    response = client.post('/api/cancel', json={
        'booking_id': 'BK-FAKE-999'
    })
    assert response.status_code == 404

def test_bulk_discount(client, mock_db):
    mock_db.offers.insert_one({
        'name': 'Buy 3 Get 1 Free',
        'code': None,
        'type': 'bulk',
        'buy_seats': 3,
        'get_seats': 1,
        'active': True
    })

    movie = mock_db.movies.insert_one({
        'name': 'Discount Test',
        'genre': 'Action',
        'timings': ['5:00 PM'],
        'total_seats': 100,
        'price_per_seat': 100
    })

    response = client.post('/api/book', json={
        'movie_id': str(movie.inserted_id),
        'contact_number': '1234567890',
        'booking_date': '2026-04-23',
        'timing': '5:00 PM',
        'seats': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['seats_booked'] == 6
    assert data['total_price'] == 400

def test_coupon_discount(client, mock_db):
    mock_db.offers.insert_one({
        'name': 'Buy 3 Get 1 Free',
        'code': None,
        'type': 'bulk',
        'buy_seats': 3,
        'get_seats': 1,
        'active': True
    })
    mock_db.offers.insert_one({
        'name': '20% Off',
        'code': 'SAVE20',
        'type': 'coupon',
        'discount_percent': 20,
        'active': True
    })

    movie = mock_db.movies.insert_one({
        'name': 'Coupon Test',
        'genre': 'Action',
        'timings': ['5:00 PM'],
        'total_seats': 100,
        'price_per_seat': 100
    })

    response = client.post('/api/book', json={
        'movie_id': str(movie.inserted_id),
        'contact_number': '1234567890',
        'booking_date': '2026-04-23',
        'timing': '5:00 PM',
        'seats': ['A1', 'A2', 'A3', 'A4', 'A5'],
        'coupon_code': 'SAVE20'
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data['coupon_code'] == 'SAVE20'
    assert data['seats_booked'] == 5
    assert data['total_price'] == 320

def test_add_offer(client, mock_db):
    response = client.post('/api/offers', json={
        'name': 'Buy 5 Get 2 Free',
        'type': 'bulk',
        'buy_seats': 5,
        'get_seats': 2
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['name'] == 'Buy 5 Get 2 Free'
    assert data['buy_seats'] == 5
    assert data['get_seats'] == 2

def test_delete_offer(client, mock_db):
    offer = mock_db.offers.insert_one({
        'name': 'Test Offer',
        'type': 'bulk',
        'min_seats': 3,
        'discount_seats': 1,
        'active': True
    })

    response = client.delete(f'/api/offers/{str(offer.inserted_id)}')
    assert response.status_code == 200

    assert mock_db.offers.find_one({'_id': offer.inserted_id}) is None