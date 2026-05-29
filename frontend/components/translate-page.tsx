"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import MarkdownContent from "./markdown-content";
import type { TranslateRecord } from "./translate-app";

interface Props {
  record: TranslateRecord | null;
  initPdfUrl: string;
  initProductName: string;
  onSave: (record: TranslateRecord) => void;
}

export default function TranslateContent({
  record,
  initPdfUrl,
  initProductName,
  onSave,
}: Props) {
  const [summary, setSummary] = useState(record?.summary ?? "");
  const [disclaimer, setDisclaimer] = useState(record?.disclaimer ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // upload mode state
  const [file, setFile] = useState<File | null>(null);
  const [uploadName, setUploadName] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const startedRef = useRef(false);

  // auto-start if URL provided; ref prevents StrictMode double-invoke
  useEffect(() => {
    if (!initPdfUrl || record || startedRef.current) return;
    startedRef.current = true;
    runUrlTranslate(initPdfUrl, initProductName);
  }, []);

  async function runUrlTranslate(url: string, name: string) {
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_url: url, product_name: name }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setSummary(data.summary);
      setDisclaimer(data.disclaimer);
      onSave({
        id: Date.now().toString(),
        title: name || "未命名保單",
        createdAt: Date.now(),
        summary: data.summary,
        disclaimer: data.disclaimer,
      });
    } catch {
      setError("保單解析失敗，請確認保單連結是否有效，或稍後再試。");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setLoading(true);
    setError("");

    const formData = new FormData();
    formData.append("file", file);
    formData.append("product_name", uploadName);

    try {
      const res = await fetch("/api/translate/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      setSummary(data.summary);
      setDisclaimer(data.disclaimer);
      onSave({
        id: Date.now().toString(),
        title: uploadName || file.name.replace(/\.pdf$/i, ""),
        createdAt: Date.now(),
        summary: data.summary,
        disclaimer: data.disclaimer,
      });
    } catch {
      setError("保單解析失敗，請確認檔案是否為有效的 PDF。");
    } finally {
      setLoading(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.type === "application/pdf") setFile(dropped);
  }

  const isUrlMode = !!initPdfUrl;
  const displayName = record?.title || (isUrlMode ? initProductName : uploadName || file?.name || "");
  const showUploadForm = !record && !isUrlMode && !summary && !loading;
  const showResult = !!(record?.summary || summary);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <Link href="/products" className="text-sm text-gray-400 hover:text-gray-600 transition-colors">
            ← 返回商品列表
          </Link>
          <div className="mt-3 flex items-center gap-3">
            <span className="text-xs px-2.5 py-1 bg-blue-100 text-blue-700 rounded-full font-medium">
              保單白話文
            </span>
            {displayName && (
              <h1 className="text-lg font-semibold text-gray-800 truncate">{displayName}</h1>
            )}
          </div>
        </div>

        {/* Upload form */}
        {showUploadForm && (
          <div className="space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-2xl px-6 py-14 cursor-pointer transition-colors ${
                dragging
                  ? "border-blue-400 bg-blue-50"
                  : file
                  ? "border-blue-300 bg-blue-50"
                  : "border-gray-300 bg-white hover:border-blue-300 hover:bg-gray-50"
              }`}
            >
              <PdfIcon active={!!file} />
              {file ? (
                <>
                  <p className="text-sm font-medium text-blue-700">{file.name}</p>
                  <p className="text-xs text-gray-400">
                    {(file.size / 1024 / 1024).toFixed(1)} MB・點此更換檔案
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm font-medium text-gray-600">點此上傳或拖曳 PDF 保單</p>
                  <p className="text-xs text-gray-400">僅支援 .pdf 格式</p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) setFile(f); }}
              />
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1.5">保單名稱（選填）</label>
              <input
                type="text"
                value={uploadName}
                onChange={(e) => setUploadName(e.target.value)}
                placeholder="例：南山人壽美利年年增額終身壽險"
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </div>

            {error && <p className="text-sm text-red-500">{error}</p>}

            <button
              onClick={handleUpload}
              disabled={!file}
              className="w-full py-3 bg-blue-700 text-white rounded-xl text-sm font-medium hover:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              開始翻譯
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-8 h-8 border-2 border-blue-700 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-600">正在解析保單條款，請稍候...</p>
            <p className="text-xs text-gray-400">通常需要 15–30 秒</p>
          </div>
        )}

        {/* URL-mode error */}
        {error && isUrlMode && (
          <div className="py-16 flex flex-col items-center gap-4">
            <p className="text-sm text-red-500">{error}</p>
            <Link href="/products" className="text-sm text-blue-700 hover:underline">返回商品列表</Link>
          </div>
        )}

        {/* Result */}
        {showResult && (
          <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
            <div className="text-sm text-gray-800 leading-relaxed">
              <MarkdownContent content={record?.summary || summary} />
            </div>
            {(record?.disclaimer || disclaimer) && (
              <p className="mt-6 pt-4 border-t border-gray-100 text-xs text-gray-400">
                {record?.disclaimer || disclaimer}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function PdfIcon({ active }: { active: boolean }) {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke={active ? "#1d4ed8" : "#9ca3af"} strokeWidth="1.5">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
      <line x1="9" y1="13" x2="15" y2="13" />
      <line x1="9" y1="17" x2="13" y2="17" />
    </svg>
  );
}
