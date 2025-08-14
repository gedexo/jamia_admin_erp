from django_tables2 import columns, TemplateColumn
from core.base import BaseTable
from .models import Memo, RequestSubmission, RequestSubmissionType

class RequestSubmissionTable(BaseTable):
    created = columns.DateTimeColumn(verbose_name="Created At", format="d/m/Y")
    request_id = columns.Column(verbose_name="Request ID")
    status = columns.TemplateColumn(
        verbose_name="Status",
        template_code="""
            {% if record.status == "approved" %}
                <span class="badge bg-success">Approved</span>
            
            {% elif record.status == "rejected" %}
                <span class="badge bg-danger">Rejected</span>
            
            {% elif request.user.usertype == "College" %}
                <span class="badge bg-warning text-white">Pending</span>
            
            {% elif record.approved_or_rejected_for_current_user|default_if_none:False %}
                {% if record.status == "approved" %}
                    <span class="badge bg-success">Approved</span>
                {% elif record.status == "rejected" %}
                    <span class="badge bg-danger">Rejected</span>
                {% endif %}
            
            {% elif record.status == "processing" or record.is_processing %}
                <span class="badge bg-primary text-white">Processing</span>
            
            {% else %}
                <span class="badge bg-warning text-white">Pending</span>
            {% endif %}
        """,
        orderable=True,
    )

    class Meta:
        model = RequestSubmission
        fields = ("request_id", "title", "college", "created", "status")
        attrs = {"class": "table key-buttons border-bottom"}

    
class MyRequestSubmissionTable(BaseTable):
    created = columns.DateTimeColumn(verbose_name="Created At", format="d/m/Y")
    request_id = columns.Column(verbose_name="Request ID")
    status = columns.TemplateColumn(
        verbose_name="Status",
        template_code="""
            {% if record.oe_assigned_to_creator %}
                {% if record.status == 'approved' %}
                    <span class="badge bg-success">Approved</span>
                {% elif record.status == 'rejected' %}
                    <span class="badge bg-danger">Rejected</span>
                {% else %}
                    <span class="badge bg-primary text-white">Processing</span>
                {% endif %}
            {% else %}
                <span class="badge bg-warning text-white">Pending</span>
            {% endif %}
        """,
        orderable=True,
    )

    class Meta:
        model = RequestSubmission
        fields = ("request_id", "title", "college", "created", "status")
        attrs = {"class": "table key-buttons border-bottom"}



class RequestSubmissionTypeTable(BaseTable):
    class Meta:
        model = RequestSubmissionType
        fields = ("title",)
        attrs = {"class": "table key-buttons border-bottom"}

class MemoTable(BaseTable):
    class Meta:
        model = Memo
        fields = ("title",)
        attrs = {"class": "table key-buttons border-bottom"}