from collections import Counter

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from elections.models import Candidate
from secure_election.utils.encryption import decrypt_vote

from .models import Vote


def export_results_pdf(modeladmin, request, queryset):
    votes = Vote.objects.all()
    decrypted_ids = []

    for vote in votes:
        try:
            cid = decrypt_vote(vote.encrypted_candidate)
            decrypted_ids.append(int(cid))
        except Exception:
            continue

    counts = Counter(decrypted_ids)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="election_results.pdf"'

    pdf = canvas.Canvas(response, pagesize=letter)
    y = 750

    pdf.setFont('Helvetica-Bold', 16)
    pdf.drawString(200, y, 'Election Results')
    y -= 40

    pdf.setFont('Helvetica', 12)

    for cid, total in counts.items():
        candidate = Candidate.objects.filter(id=cid).first()
        if candidate:
            pdf.drawString(100, y, f'{candidate.name} : {total} votes')
            y -= 25

    pdf.save()
    return response


export_results_pdf.short_description = 'Export Results as PDF'


class VoteAdmin(admin.ModelAdmin):
    list_display = ('voter', 'encrypted_candidate')
    actions = [export_results_pdf]

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)

        try:
            votes = Vote.objects.all()
            decrypted_ids = []

            for vote in votes:
                try:
                    cid = decrypt_vote(vote.encrypted_candidate)
                    decrypted_ids.append(int(cid))
                except Exception:
                    continue

            counts = Counter(decrypted_ids)

            winner_name = None
            winner_votes = 0
            if counts:
                top_id = max(counts, key=counts.get)
                winner_votes = counts[top_id]
                winner = Candidate.objects.filter(id=top_id).first()
                winner_name = winner.name if winner else None

            results_html = ''

            if winner_name:
                results_html += f"""
                <div style="background:#1e3a2f;color:#b7f7d0;padding:15px;border:1px solid #2f6f54;border-radius:8px;margin-bottom:15px;">
                    <h2 style="margin:0;color:#b7f7d0;">Winner: {winner_name} ({winner_votes} votes)</h2>
                </div>
                """

            results_html += (
                '<h3 style="margin:0 0 8px 0;color:var(--body-fg);">Decrypted Results</h3>'
                '<ul style="margin:0;padding-left:22px;color:var(--body-fg);">'
            )

            for cid, total in counts.items():
                candidate = Candidate.objects.filter(id=cid).first()
                if candidate:
                    results_html += f'<li>{candidate.name} - {total} votes</li>'

            results_html += '</ul>'

            response.context_data['decrypted_results'] = format_html(results_html)
        except Exception:
            response.context_data = response.context_data or {}
            response.context_data['decrypted_results'] = format_html(
                '<p style="color:var(--body-fg);">Unable to render decrypted results.</p>'
            )

        return response


admin.site.register(Vote, VoteAdmin)
