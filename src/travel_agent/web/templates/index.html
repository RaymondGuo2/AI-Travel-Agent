{% extends "base.html" %}
{% block title %}Book a Trip — AI Travel Agent{% endblock %}
{% block content %}
<div class="card">
  <h2>Book a Business Trip</h2>
  <p style="font-size:0.88rem;color:#666;margin-bottom:1.2rem;">
    The AI agent will autonomously book flights, hotel, and ground transport within company policy.
  </p>
  <form id="trip-form">
    <div class="grid-2">
      <div>
        <label>Traveler Name</label>
        <input type="text" name="traveler_name" placeholder="Jane Smith" required>
      </div>
      <div>
        <label>Traveler Email</label>
        <input type="email" name="traveler_email" placeholder="jane@company.com" required>
      </div>
    </div>
    <div class="grid-2">
      <div>
        <label>Origin (IATA code)</label>
        <input type="text" name="origin" placeholder="SFO" required maxlength="3" style="text-transform:uppercase">
      </div>
      <div>
        <label>Destination (IATA code)</label>
        <input type="text" name="destination" placeholder="JFK" required maxlength="3" style="text-transform:uppercase">
      </div>
    </div>
    <div class="grid-2">
      <div>
        <label>Departure Date</label>
        <input type="date" name="departure_date" required>
      </div>
      <div>
        <label>Return Date (optional)</label>
        <input type="date" name="return_date">
      </div>
    </div>
    <label>Purpose of Travel</label>
    <input type="text" name="purpose" placeholder="Client meeting, conference, training..." required>
    <div class="grid-2" style="margin-bottom:1rem">
      <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0">
        <input type="checkbox" name="needs_hotel" checked style="width:auto;margin-bottom:0">
        Include hotel booking
      </label>
      <label style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0">
        <input type="checkbox" name="needs_ground_transport" checked style="width:auto;margin-bottom:0">
        Include ground transport
      </label>
    </div>
    <button type="submit" class="btn btn-primary">Book Trip →</button>
  </form>
</div>

<div id="result" style="display:none">
  <div class="card">
    <h2>Booking Status</h2>
    <div id="status-content"></div>
  </div>
</div>

<script>
const form = document.getElementById('trip-form');
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(form).entries());
  data.needs_hotel = form.needs_hotel.checked;
  data.needs_ground_transport = form.needs_ground_transport.checked;
  if (!data.return_date) delete data.return_date;

  document.getElementById('result').style.display = 'block';
  document.getElementById('status-content').innerHTML =
    '<div class="alert alert-info">⏳ Submitting trip request...</div>';

  try {
    const res = await fetch('/api/trips', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(data),
    });
    const trip = await res.json();
    if (!res.ok) throw new Error(trip.detail || 'Failed to submit trip');

    document.getElementById('status-content').innerHTML =
      `<div class="alert alert-info">
        ✅ Trip submitted! ID: <strong>${trip.trip_id}</strong><br>
        The AI agent is now booking your travel...<br>
        <a href="/trips/${trip.trip_id}">Track booking status →</a>
      </div>`;

    // Poll for completion
    pollStatus(trip.trip_id);
  } catch (err) {
    document.getElementById('status-content').innerHTML =
      `<div class="alert" style="background:#fdedec;color:#c0392b;border:1px solid #f5b7b1">
        ❌ Error: ${err.message}
      </div>`;
  }
});

async function pollStatus(tripId) {
  for (let i = 0; i < 60; i++) {
    await new Promise(r => setTimeout(r, 3000));
    const res = await fetch(`/api/trips/${tripId}`);
    const trip = await res.json();
    if (['booked', 'escalated', 'failed'].includes(trip.status)) {
      window.location.href = `/trips/${tripId}`;
      return;
    }
  }
}
</script>
{% endblock %}
