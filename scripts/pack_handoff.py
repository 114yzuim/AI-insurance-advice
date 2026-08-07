import zipfile, pathlib, os

ROOT = pathlib.Path(".")
OUT = pathlib.Path("../ai_insurance_b2c_handoff.zip")
README_SRC = pathlib.Path("../README_整合說明.md")

INCLUDE = [
    "backend/routers/chat.py",
    "backend/routers/products.py",
    "backend/routers/translate.py",
    "backend/routers/needs_assessment.py",
    "backend/routers/claims.py",
    "backend/routers/__init__.py",
    "backend/services/claude_service.py",
    "backend/services/rag_service.py",
    "backend/services/pdf_rag_service.py",
    "backend/services/pdf_service.py",
    "backend/services/profile_rag_service.py",
    "backend/services/product_service.py",
    "backend/services/needs_assessment_service.py",
    "backend/services/claims_service.py",
    "backend/services/__init__.py",
    "backend/data/crawled_products_with_pdf_dm_links.json",
    "backend/data/selected_products.json",
    "backend/requirements.txt",
    "frontend/app/chat/page.tsx",
    "frontend/app/products/page.tsx",
    "frontend/app/translate/page.tsx",
    "frontend/app/health-check/page.tsx",
    "frontend/app/claims/page.tsx",
    "frontend/app/api/chat/route.ts",
    "frontend/app/api/chat/upload/route.ts",
    "frontend/app/api/products/route.ts",
    "frontend/app/api/translate/route.ts",
    "frontend/app/api/translate/upload/route.ts",
    "frontend/app/api/needs-assessment/route.ts",
    "frontend/app/api/claims/route.ts",
    "frontend/components/chat-app.tsx",
    "frontend/components/chat-interface.tsx",
    "frontend/components/chat-sidebar.tsx",
    "frontend/components/chat-landing.tsx",
    "frontend/components/product-card.tsx",
    "frontend/components/product-list.tsx",
    "frontend/components/product-chat-panel.tsx",
    "frontend/components/translate-app.tsx",
    "frontend/components/translate-page.tsx",
    "frontend/components/translate-sidebar.tsx",
    "frontend/components/claims-app.tsx",
    "frontend/components/health-check-app.tsx",
    "frontend/components/health-check-sidebar.tsx",
    "frontend/components/markdown-content.tsx",
    "frontend/components/font-size-toggle.tsx",
    "frontend/components/nav-links.tsx",
]

pdf_files = [
    f"backend/data/pdfs/{p.name}"
    for p in (ROOT / "backend/data/pdfs").iterdir()
    if p.suffix == ".pdf"
]

chroma_files = []
for dirpath, dirnames, filenames in os.walk(ROOT / "backend/chroma_db"):
    for f in filenames:
        full = pathlib.Path(dirpath) / f
        rel = full.relative_to(ROOT).as_posix()
        chroma_files.append(rel)

OUT.unlink(missing_ok=True)
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for rel in INCLUDE + pdf_files + chroma_files:
        zf.write(ROOT / rel, rel)
    zf.write(README_SRC, "INTEGRATION_README.md")

size_mb = OUT.stat().st_size / 1024 / 1024
total = len(INCLUDE) + len(pdf_files) + len(chroma_files) + 1
print(f"Done: {OUT.name} ({size_mb:.1f} MB), {total} files")
print(f"  source files : {len(INCLUDE)}")
print(f"  PDFs         : {len(pdf_files)}")
print(f"  chroma_db    : {len(chroma_files)} files")
