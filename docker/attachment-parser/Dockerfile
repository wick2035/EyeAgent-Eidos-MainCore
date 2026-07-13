FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY docker/attachment-parser/requirements.txt /tmp/attachment-parser-requirements.txt
RUN pip install --no-cache-dir -r /tmp/attachment-parser-requirements.txt \
    && groupadd --gid 65532 attachmentparser \
    && useradd --uid 65532 --gid 65532 --no-create-home --shell /usr/sbin/nologin attachmentparser \
    && mkdir -p /app/infrastructure/attachments /app/utils \
    && chown -R 65532:65532 /app

COPY --chown=65532:65532 infrastructure/attachments/parser_protocol.py /app/infrastructure/attachments/parser_protocol.py
COPY --chown=65532:65532 infrastructure/attachments/attachment_parser_worker.py /app/infrastructure/attachments/attachment_parser_worker.py
COPY --chown=65532:65532 infrastructure/attachments/research_text_contract.py /app/infrastructure/attachments/research_text_contract.py
COPY --chown=65532:65532 infrastructure/attachments/research_docx_contract.py /app/infrastructure/attachments/research_docx_contract.py
COPY --chown=65532:65532 utils/pdf_utils.py /app/utils/pdf_utils.py

USER 65532:65532

ENTRYPOINT ["python", "-m", "infrastructure.attachments.attachment_parser_worker"]
