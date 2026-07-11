from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from .models import ProgramDocument
from .policies import can_view_program_documents


@login_required
def program_document_download(request, public_id):
    document = get_object_or_404(ProgramDocument, public_id=public_id)
    if not can_view_program_documents(request.user):
        raise PermissionDenied
    return FileResponse(
        document.document_file.open("rb"),
        as_attachment=True,
        filename=document.original_filename,
    )
