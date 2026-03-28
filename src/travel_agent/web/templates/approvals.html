{% extends "base.html" %}
{% block title %}Pending Approvals — AI Travel Agent{% endblock %}
{% block content %}
<div class="card">
  <h2>Pending Approvals</h2>
  {% if not escalations %}
    <p style="color:#666;font-size:0.9rem">No pending approvals.</p>
  {% else %}
    {% for e in escalations %}
    <div style="border:1px solid #eee;border-radius:6px;padding:1rem;margin-bottom:1rem">
      <div style="display:flex;justify-content:space-between;align-items:start">
        <div>
          <p><strong>Trip ID:</strong> {{ e.trip_id[:8] }}...</p>
          <p><strong>Reason:</strong> {{ e.reason }}</p>
          <p><strong>Total:</strong> ${{ "%.2f"|format(e.details.get("trip_total_usd", 0)) }}</p>
          <p style="font-size:0.8rem;color:#888">Created: {{ e.created_at[:19].replace("T"," ") }}</p>
        </div>
        <span class="status-badge status-{{ e.status }}">{{ e.status }}</span>
      </div>
      <div style="margin-top:0.75rem">
        <a href="/approvals/{{ e.id }}" class="btn btn-primary" style="font-size:0.85rem">Review →</a>
      </div>
    </div>
    {% endfor %}
  {% endif %}
</div>
{% endblock %}
