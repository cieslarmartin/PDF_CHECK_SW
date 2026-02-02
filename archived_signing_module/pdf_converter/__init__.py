# pdf_converter/__init__.py
# Modul pro konverzi PDF, odstranění podpisů a podepisování
# Build 1.0 | © 2025 Ing. Martin Cieślar

from .signature_remover import remove_signatures, remove_signatures_batch
from .pdfa_converter import convert_to_pdfa, convert_to_pdfa_batch
from .batch_processor import process_pdf_batch, ProcessingOptions
from .signer import sign_pdf, sign_pdf_batch, SigningOptions, find_pkcs11_library, list_certificates_from_token

__all__ = [
    'remove_signatures',
    'remove_signatures_batch',
    'convert_to_pdfa',
    'convert_to_pdfa_batch',
    'process_pdf_batch',
    'ProcessingOptions',
    'sign_pdf',
    'sign_pdf_batch',
    'SigningOptions',
    'find_pkcs11_library',
    'list_certificates_from_token'
]
