{% extends "base.html" %}
{% block title %}Trip {{ trip_id[:8] }} — AI Travel Agent{% endblock %}
{% block content %}
<div class="card">
  <h2>Trip Status</h2>
  <p style="font-size:0.85rem;color:#666;margin-bottom:1rem">ID: {{ trip_id }}</p>
  <p>
    Status: <span class="status-badge status-{{ status }}">{{ status }}</span>
    {% if total_cost_usd %}
    &nbsp;|&nbsp; Total: <strong>${{ "%.2f"|format(total_cost_usd) }}</strong>
    {% endif %}
  </p>
</div>

{% if status == "escalated" and escalation_id %}
<div class="card">
  <h2>⚠ Approval Required</h2>
  <p class="alert alert-warning" style="margin-bottom:1rem">
    This trip requires manager approval before it can be booked.
    <a href="/approvals/{{ escalation_id }}">Review and approve →</a>
  </p>
</div>
{% endif %}

{% if status == "failed" and error %}
<div class="card">
  <h2>Booking Failed</h2>
  <div class="alert" style="background:#fdedec;color:#c0392b;border:1px solid #f5b7b1">{{ error }}</div>
</div>
{% endif %}

{% if itinerary %}
<div class="card">
  <h2>Itinerary</h2>
  <pre>{{ itinerary }}</pre>
</div>
{% elif status in ["planning", "searching", "booking", "policy_check"] %}
<div class="card">
  <div class="alert alert-info">
    ⏳ The AI agent is working on your booking...
    <script>setTimeout(() => location.reload(), 4000);</script>
  </div>
</div>
{% endif %}
{% endblock %}
