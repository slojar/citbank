from threading import Thread
from django.utils import timezone

from coporate.models import TransferScheduler, TransferRequest, BulkUploadFile
from coporate.utils import perform_corporate_transfer, scheduler_next_job

present_time = timezone.datetime.now()
transfer_scheduler = TransferScheduler.objects.filter(
    status="active", next_job_date=present_time, end_date__gte=present_time, completed=False
)


# Cron to run transfer scheduler
def transfer_scheduler_job(request):
    # Get all transfer request mapped to schedulers
    for scheduler in transfer_scheduler:
        scheduler_next_job(scheduler)
        transfer_requests = TransferRequest.objects.filter(scheduler=scheduler, approved=True, status="approved")
        for trans_req in transfer_requests:
            Thread(target=perform_corporate_transfer, args=[request, trans_req, "single"]).start()

    return "Transfer Scheduler Job ran successfully"


def delete_uploaded_files():
    # Get all used uploads
    BulkUploadFile.objects.filter(used=True).delete()
    return "Upload deletion job ran successfully"
