let currentBookMovieId = null;
let currentBookPrice = 100;
let currentBookTimings = [];
let currentBookTotalSeats = 0;
let currentBookMovieData = null;

document.addEventListener('DOMContentLoaded', () => {
    loadMovies();

    const searchDate = document.getElementById('searchDate');
    const today = new Date().toISOString().split('T')[0];
    searchDate.min = today;
    searchDate.value = today;

    document.getElementById('movieForm').addEventListener('submit', (e) => {
        e.preventDefault();
        addMovie();
    });

    document.getElementById('bookingDate').addEventListener('change', function() {
        if (currentBookMovieId) {
            updateTimingAvailability(this.value);
        }
    });
});

function loadMovies(search = '') {
    const dateParam = document.getElementById('searchDate').value;
    let url = '/api/movies';
    const params = [];
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (dateParam) params.push(`date=${dateParam}`);
    if (params.length > 0) url += '?' + params.join('&');

    fetch(url)
        .then(res => res.json())
        .then(movies => {
            const grid = document.getElementById('moviesGrid');
            grid.innerHTML = '';
            if (movies.length === 0) {
                grid.innerHTML = '<div class="no-movies"><p>No movies found</p></div>';
            } else {
                movies.forEach(movie => {
                    const card = createMovieCard(movie, dateParam);
                    grid.appendChild(card);
                });
            }
        })
        .catch(err => console.error('Error loading movies:', err));
}

function createMovieCard(movie, selectedDate) {
    const card = document.createElement('div');
    card.className = 'movie-card';
    card.id = `movie-${movie.id}`;

    const price = movie.price_per_seat;
    const priceText = price ? `Rs. ${price}/seat` : 'Price not set';
    const timings = movie.timings || [];
    const totalSeats = movie.total_seats || 0;

    const timingBadges = timings.map(t => {
        const key = `available_${t.replace(" ", "_").replace(":", "")}`;
        const avail = selectedDate && movie[key] !== undefined ? movie[key] : totalSeats;
        const isFull = avail === 0;
        return `<span class="timing-badge ${isFull ? 'house-full' : ''}">${t}: ${avail} seats</span>`;
    });

    const timingsJson = JSON.stringify(timings).replace(/"/g, '&quot;');
    const movieName = movie.name.replace(/'/g, "&#39;");

    card.innerHTML = `
        <h3>${movie.name}</h3>
        <div class="movie-info">
            <span>${movie.genre || 'N/A'}</span>
            <span class="price-tag">${priceText}</span>
        </div>
        <div class="movie-timings">${timingBadges.join('')}</div>
        <div class="card-actions">
            <button class="btn-primary book-btn" onclick="handleBookClick('${movie.id}', '${movieName}', ${price || 0}, '${timingsJson}', ${totalSeats})">Book</button>
        </div>
    `;

    return card;
}

function addMovie() {
    const name = document.getElementById('movieName').value.trim();
    const genre = document.getElementById('movieGenre').value.trim();
    const timingsInput = document.getElementById('movieTimings').value.trim();
    const totalSeats = parseInt(document.getElementById('movieSeats').value);
    const rows = parseInt(document.getElementById('movieRows').value) || 10;
    const seatsPerRow = parseInt(document.getElementById('movieSeatsPerRow').value) || 20;
    const price = document.getElementById('moviePrice').value ? parseInt(document.getElementById('moviePrice').value) : null;

    if (!name || !totalSeats) {
        alert('Please fill in movie name and total seats');
        return;
    }

    const timings = timingsInput ? timingsInput.split(',').map(t => t.trim()).filter(t => t) : [];

    const body = {
        name: name,
        genre: genre,
        timings: timings,
        total_seats: totalSeats,
        rows: rows,
        seats_per_row: seatsPerRow
    };
    if (price) body.price_per_seat = price;

    fetch('/api/movies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => Promise.reject(err));
        }
        return res.json();
    })
    .then(movie => {
        const grid = document.getElementById('moviesGrid');
        const card = createMovieCard(movie);
        grid.prepend(card);
        document.getElementById('movieForm').reset();
    })
    .catch(err => {
        alert(err.error || 'Failed to add movie');
    });
}

function handleBookClick(id, name, price, timingsJson, totalSeats) {
    fetch(`/api/movies/${id}`)
    .then(res => res.json())
    .then(movie => {
        var timings = movie.timings || [];
        openBookModal(id, name, price || movie.price_per_seat, timings, movie.total_seats, movie);
    })
    .catch(err => {
        try {
            var timings = JSON.parse(timingsJson);
        } catch(e) {
            timings = [];
        }
        openBookModal(id, name, price, timings, totalSeats);
    });
}

function openBookModal(id, name, price, timings, totalSeats, movieData) {
    currentBookMovieId = id;
    currentBookPrice = price || 100;
    currentBookTimings = timings || [];
    currentBookTotalSeats = totalSeats || 0;
    currentBookMovieData = movieData;
    selectedSeats = [];

    const today = new Date().toISOString().split('T')[0];
    document.getElementById('bookingDate').min = today;
    document.getElementById('bookingDate').value = today;

    document.getElementById('modalMovieName').textContent = name;
    document.getElementById('modalPrice').textContent = `Rs. ${currentBookPrice}/seat`;
    document.getElementById('customerPhone').value = '';
    document.getElementById('couponCode').value = '';

    document.getElementById('step1').classList.remove('hidden');
    document.getElementById('step2').classList.add('hidden');

    updateTimingAvailability(today);
    document.getElementById('bookModal').style.display = 'flex';
}

function onDateChange() {
    const date = document.getElementById('bookingDate').value;
    if (date) updateTimingAvailability(date);
}

function goToSeatSelection() {
    const phone = document.getElementById('customerPhone').value.trim();
    if (!phone) {
        alert('Please enter your mobile number');
        return;
    }
    if (!selectedTiming) {
        alert('Please select a show timing');
        return;
    }
    
    document.getElementById('step1').classList.add('hidden');
    document.getElementById('step2').classList.remove('hidden');
    renderSeatLayout();
}

function goBackToDetails() {
    document.getElementById('step2').classList.add('hidden');
    document.getElementById('step1').classList.remove('hidden');
}

function renderSeatLayout() {
    const layout = document.getElementById('seatLayout');
    layout.innerHTML = '';
    
    const bookingDate = document.getElementById('bookingDate').value;
    
    fetch(`/api/movies/${currentBookMovieId}`)
    .then(res => res.json())
    .then(movie => {
        const movieRows = movie.rows || 10;
        const seatsPerRow = movie.seats_per_row || 14;
        const totalSeats = movie.total_seats || (movieRows * seatsPerRow);
        const actualRows = Math.ceil(totalSeats / seatsPerRow);
        
        return fetch(`/api/movies/${currentBookMovieId}/seats?date=${bookingDate}&timing=${encodeURIComponent(selectedTiming)}`)
        .then(res => res.json())
        .then(data => {
            const occupiedSeats = data.booked_seats || [];
            renderSeats(layout, actualRows, seatsPerRow, occupiedSeats);
        });
    })
    .catch(err => {
        console.error('Error loading movie:', err);
        renderSeats(layout, 10, 14, []);
    });
}

function renderSeats(layout, rows, seatsPerRow, occupiedSeats) {
    for (let r = 0; r < rows; r++) {
        const rowDiv = document.createElement('div');
        rowDiv.className = 'seat-row';
        
        const rowLabel = String.fromCharCode(65 + r);
        
        for (let s = 1; s <= seatsPerRow; s++) {
            const seatNum = `${rowLabel}${s}`;
            const isOccupied = occupiedSeats.includes(seatNum);
            
            const seat = document.createElement('div');
            seat.className = isOccupied ? 'seat occupied' : 'seat available';
            seat.dataset.seat = seatNum;
            
            if (!isOccupied) {
                seat.onclick = () => toggleSeat(seat, seatNum);
            }
            seat.textContent = s;
            rowDiv.appendChild(seat);
        }
        
        const rowLabelEl = document.createElement('span');
        rowLabelEl.className = 'row-label';
        rowLabelEl.textContent = rowLabel;
        rowDiv.insertBefore(rowLabelEl, rowDiv.firstChild);
        
        layout.appendChild(rowDiv);
    }
    
    updateSeatSummary();
}

function toggleSeat(seatEl, seatNum) {
    if (seatEl.classList.contains('occupied')) return;
    
    if (seatEl.classList.contains('selected')) {
        seatEl.classList.remove('selected');
        seatEl.classList.add('available');
        selectedSeats = selectedSeats.filter(s => s !== seatNum);
    } else {
        seatEl.classList.remove('available');
        seatEl.classList.add('selected');
        selectedSeats.push(seatNum);
    }
    updateSeatSummary();
}

function updateSeatSummary() {
    const coupon = document.getElementById('couponCode').value.trim().toUpperCase();
    const seatsCount = selectedSeats.length;
    const basePrice = seatsCount * currentBookPrice;
    
    let bulkFreeSeats = 0;
    if (seatsCount >= 3) {
        bulkFreeSeats = Math.floor(seatsCount / 4);
    }
    
    const priceAfterBulk = (seatsCount - bulkFreeSeats) * currentBookPrice;
    
    let couponDiscount = 0;
    if (coupon === 'SAVE20') couponDiscount = 0.2;
    else if (coupon === 'SAVE10') couponDiscount = 0.1;
    else if (coupon === 'SAVE30') couponDiscount = 0.3;
    
    const finalPrice = Math.round(priceAfterBulk * (1 - couponDiscount));
    const savings = basePrice - finalPrice;
    
    const summaryEl = document.getElementById('seatSummary');
    if (summaryEl) {
        summaryEl.dataset.count = seatsCount;
        summaryEl.dataset.total = finalPrice;
        summaryEl.dataset.savings = savings;
        
        let html = `<span>Selected: <strong>${seatsCount}</strong></span>`;
        html += `<span>Total: <strong>Rs. ${finalPrice}</strong></span>`;
        if (savings > 0) {
            html += `<span class="savings">You save Rs. ${savings}!</span>`;
        }
        summaryEl.innerHTML = html;
    }
}

function confirmBooking() {
    const contactNumber = document.getElementById('customerPhone').value.trim();
    const couponCode = document.getElementById('couponCode').value.trim();
    const bookingDate = document.getElementById('bookingDate').value;
    
    if (selectedSeats.length === 0) {
        alert('Please select at least one seat');
        return;
    }
    
    fetch('/api/book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            movie_id: currentBookMovieId,
            contact_number: contactNumber,
            booking_date: bookingDate,
            timing: selectedTiming,
            seats: selectedSeats,
            coupon_code: couponCode
        })
    })
    .then(res => {
        if (!res.ok) return res.json().then(err => Promise.reject(err));
        return res.json();
    })
    .then(data => {
        alert(`Booking confirmed!\nSeats: ${selectedSeats.join(', ')}\nTotal: Rs. ${data.total_price}`);
        closeModal();
        loadMovies();
    })
    .catch(err => {
        alert(err.error || 'Booking failed');
    });
}

function updateTimingAvailability(selectedDate) {
    const timingContainer = document.getElementById('timingSelection');
    timingContainer.innerHTML = '';
    const seatContainer = document.getElementById('seatSelection');

    selectedTiming = null;
    selectedTimingAvail = 0;
    selectedSeats = [];

    if (!currentBookMovieId) return;

    fetch(`/api/movies/${currentBookMovieId}/availability?date=${selectedDate}`)
        .then(res => res.json())
        .then(data => {
            const availPerTiming = data.availability || {};
            const totalSeats = data.total_seats || currentBookTotalSeats;

            if (currentBookTimings.length > 0) {
                const label = document.createElement('label');
                label.textContent = 'Select Show Timing:';
                label.className = 'timing-label';
                timingContainer.appendChild(label);

                const timingBoxes = document.createElement('div');
                timingBoxes.className = 'timing-boxes';

                currentBookTimings.forEach((timing) => {
                    const avail = availPerTiming[timing] !== undefined ? availPerTiming[timing] : totalSeats;
                    const isFull = avail === 0;
                    const box = document.createElement('div');
                    box.className = `timing-box ${isFull ? 'house-full' : ''}`;
                    box.innerHTML = `${timing}<br><small>${avail} seats</small>`;
                    if (!isFull) box.onclick = () => {
                        document.querySelectorAll('.timing-box').forEach(b => b.classList.remove('selected'));
                        box.classList.add('selected');
                        selectedTiming = timing;
                        selectedTimingAvail = avail;
                    };
                    if (isFull) box.style.cursor = 'not-allowed';
                    box.dataset.timing = timing;
                    box.dataset.available = avail;
                    timingBoxes.appendChild(box);
                });

                timingContainer.appendChild(timingBoxes);
            }
        })
        .catch(err => console.error('Error loading availability:', err));
}

let selectedSeats = [];

function selectTiming(box, timing, avail) {
    document.querySelectorAll('.timing-box').forEach(b => b.classList.remove('selected'));
    box.classList.add('selected');
    selectedTiming = timing;
    selectedTimingAvail = avail;
}

function closeModal() {
    document.getElementById('bookModal').style.display = 'none';
    currentBookMovieId = null;
    selectedTiming = null;
    selectedTimingAvail = 0;
}

function bookTicket(movieId) {
    const bookingDate = document.getElementById('bookingDate').value;
    const contactNumber = document.getElementById('customerPhone').value.trim();
    const couponCode = document.getElementById('couponCode').value.trim();

    if (!bookingDate) {
        alert('Please select a date');
        return;
    }
    if (!selectedTiming) {
        alert('Please select a show timing');
        return;
    }
    if (selectedSeats.length === 0) {
        alert('Please select at least one seat');
        return;
    }
    if (!contactNumber) {
        alert('Please enter your contact number');
        return;
    }

    fetch('/api/book', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            movie_id: movieId,
            contact_number: contactNumber,
            booking_date: bookingDate,
            timing: selectedTiming,
            seats: selectedSeats,
            coupon_code: couponCode
        })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => Promise.reject(err));
        }
        return res.json();
    })
    .then(data => {
        let message = `Booking confirmed! Booking ID: ${data.booking_id}\nSeats: ${selectedSeats.join(', ')}`;
        if (data.bulk_savings > 0) {
            message += `\nBulk discount: Rs.${data.bulk_savings} saved!`;
        }
        if (data.coupon_savings > 0) {
            message += `\nCoupon applied: Rs.${data.coupon_savings} saved!`;
        }
        alert(message);
        selectedTiming = null;
        selectedTimingAvail = 0;
        selectedSeats = [];
        closeModal();
        loadMovies(document.getElementById('searchInput').value);
        loadBookings();
    })
    .catch(err => {
        alert(err.error || 'Booking failed');
    });
}

function cancelTicket(bookingId) {
    if (!confirm('Cancel this booking?')) return;

    fetch('/api/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ booking_id: bookingId })
    })
    .then(res => {
        if (!res.ok) {
            return res.json().then(err => Promise.reject(err));
        }
        return res.json();
    })
    .then(() => {
        loadMovies(document.getElementById('searchInput').value);
        loadBookings();
    })
    .catch(err => {
        alert(err.error || 'Cancel failed');
    });
}

function loadBookings() {
    fetch('/api/bookings')
        .then(res => res.json())
        .then(bookings => {
            const tbody = document.getElementById('bookingsBody');
            tbody.innerHTML = '';
            bookings.forEach(booking => {
                const row = document.createElement('tr');
                const bookingDate = booking.booking_date ? new Date(booking.booking_date).toLocaleDateString() : 'N/A';
                const bookingTime = booking.timing || 'N/A';
                const seatsList = booking.seats ? booking.seats.join(', ') : 'N/A';
                row.innerHTML = `
                    <td>${booking.booking_id}</td>
                    <td>${booking.movie_name}</td>
                    <td>${bookingDate}</td>
                    <td>${bookingTime}</td>
                    <td>${booking.contact_number || 'N/A'}</td>
                    <td>${seatsList}</td>
                    <td>Rs. ${booking.total_price || 'N/A'}</td>
                    <td><button class="btn-danger" onclick="cancelTicket('${booking.booking_id}')">Cancel</button></td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(err => console.error('Error loading bookings:', err));
}

function searchMovie() {
    const value = document.getElementById('searchInput').value;
    loadMovies(value);
}

function updatePriceBreakdown() {
    const coupon = document.getElementById('couponCode').value.trim().toUpperCase();
    const seatsCount = selectedSeats.length;
    const basePrice = seatsCount * currentBookPrice;

    document.getElementById('selectedSeatsCount').textContent = seatsCount;

    let bulkDiscountSeats = 0;
    let couponDiscountSeats = 0;

    if (seatsCount >= 3) {
        bulkDiscountSeats = Math.floor(seatsCount / 3);
    }

    if (coupon === 'SAVE20') couponDiscountSeats = seatsCount * 0.2;
    else if (coupon === 'SAVE10') couponDiscountSeats = seatsCount * 0.1;
    else if (coupon === 'SAVE30') couponDiscountSeats = seatsCount * 0.3;

    const bulkDiscountAmount = bulkDiscountSeats * currentBookPrice;
    const priceAfterBulk = basePrice - bulkDiscountAmount;
    const couponDiscountAmount = couponDiscountSeats * currentBookPrice;
    const totalPrice = Math.max(priceAfterBulk - couponDiscountAmount, currentBookPrice);

    document.getElementById('basePrice').textContent = `Rs. ${basePrice}`;

    const bulkRow = document.getElementById('bulkDiscountRow');
    const couponRow = document.getElementById('couponDiscountRow');

    if (bulkDiscountSeats > 0) {
        bulkRow.style.display = 'flex';
        document.getElementById('bulkDiscountAmount').textContent = `-Rs. ${bulkDiscountAmount}`;
    } else {
        bulkRow.style.display = 'none';
    }

    if (coupon && couponDiscountSeats > 0) {
        couponRow.style.display = 'flex';
        document.getElementById('couponCodeDisplay').textContent = coupon;
        document.getElementById('couponDiscountAmount').textContent = `-Rs. ${couponDiscountAmount}`;
    } else {
        couponRow.style.display = 'none';
    }

    document.getElementById('totalPrice').textContent = `Rs. ${totalPrice}`;
}

function deleteMovie(id) {
    if (!confirm('Delete this movie? All bookings for this movie will also be deleted.')) return;

    fetch(`/api/movies/${id}`, { method: 'DELETE' })
        .then(res => {
            if (!res.ok) {
                return res.json().then(err => Promise.reject(err));
            }
            return res.json();
        })
        .then(() => {
            const card = document.getElementById(`movie-${id}`);
            if (card) card.remove();
            loadBookings();
        })
        .catch(err => {
            alert(err.error || 'Delete failed');
        });
}