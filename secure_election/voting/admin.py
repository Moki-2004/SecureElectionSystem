from collections import Counter

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from elections.models import Candidate
from secure_election.utils.encryption import decrypt_vote

from .models import Vote


def _escape_pdf_text(value):
    return (
        str(value)
        .replace('\\', '\\\\')
        .replace('(', '\\(')
        .replace(')', '\\)')
    )


def _build_simple_pdf(lines):
    content_lines = ['BT', '/F1 16 Tf', '72 760 Td', f'({_escape_pdf_text(lines[0])}) Tj']
    y_step = 24

    if len(lines) > 1:
        content_lines.append('/F1 12 Tf')
        for line in lines[1:]:
            content_lines.append(f'0 -{y_step} Td')
            content_lines.append(f'({_escape_pdf_text(line)}) Tj')

    content_lines.append('ET')
    stream = '\n'.join(content_lines).encode('latin-1', errors='replace')

    objects = []
    objects.append(b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n')
    objects.append(b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n')
    objects.append(
        b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n'
    )
    objects.append(b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n')
    objects.append(
        f'5 0 obj << /Length {len(stream)} >> stream\n'.encode('latin-1') +
        stream +
        b'\nendstream endobj\n'
    )

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]

    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_offset = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n'.encode('latin-1'))
    pdf.extend(b'0000000000 65535 f \n')

    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('latin-1'))

    pdf.extend(
        (
            f'trailer << /Size {len(offsets)} /Root 1 0 R >>\n'
            f'startxref\n{xref_offset}\n%%EOF'
        ).encode('latin-1')
    )
    return bytes(pdf)


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

    lines = ['Election Results']

    if not counts:
        lines.append('No votes available.')

    for cid, total in counts.items():
        candidate = Candidate.objects.filter(id=cid).first()
        if candidate:
            lines.append(f'{candidate.name} : {total} votes')

    response = HttpResponse(_build_simple_pdf(lines), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="election_results.pdf"'
    return response


export_results_pdf.short_description = 'Export Results as PDF'


class VoteAdmin(admin.ModelAdmin):
    list_display = ('voter', 'encrypted_candidate')
    actions = [export_results_pdf]

    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        if not hasattr(response, 'context_data'):
            return response

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

            response.context_data = response.context_data or {}
            response.context_data['decrypted_results'] = format_html(results_html)
        except Exception:
            response.context_data = getattr(response, 'context_data', {}) or {}
            response.context_data['decrypted_results'] = format_html(
                '<p style="color:var(--body-fg);">Unable to render decrypted results.</p>'
            )

        return response


admin.site.register(Vote, VoteAdmin)
