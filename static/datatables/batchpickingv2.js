{% block extra_script %}
<script>
  window.NAMA_PICKLIST = "{{ nama_picklist }}";
  window.CSRF_TOKEN = "{{ csrf_token }}";
  window.CURRENT_USER = "{{ request.user.username }}";
</script>
<script src="{% static 'datatables/batchpickingv2.js' %}"></script>
{% endblock %}
