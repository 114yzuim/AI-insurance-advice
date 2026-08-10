"use client";

import { useEffect, useRef, useState } from "react";
import type { CustomerProfile } from "./health-check-app";

interface Props {
  profiles: CustomerProfile[];
  currentId: string | null;
  open: boolean;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, name: string) => void;
  onToggle: () => void;
}

export default function HealthCheckSidebar({
  profiles,
  currentId,
  open,
  onNew,
  onSelect,
  onDelete,
  onRename,
  onToggle,
}: Props) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpenId) return;
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpenId(null);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [menuOpenId]);

  function commitRename() {
    if (renamingId && renameValue.trim()) onRename(renamingId, renameValue.trim());
    setRenamingId(null);
  }

  if (!open) {
    return (
      <div className="flex w-12 shrink-0 flex-col items-center gap-2 border-r border-slate-200 bg-white py-3">
        <button onClick={onToggle} className="rounded-xl p-2 text-slate-500 hover:bg-slate-100" title="展開側欄">
          <MenuIcon />
        </button>
        <button onClick={onNew} className="rounded-xl p-2 text-teal-700 hover:bg-teal-50" title="建立資料">
          <PlusIcon />
        </button>
      </div>
    );
  }

  return (
    <aside className="flex w-64 shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <span className="text-sm font-bold text-slate-700">健檢紀錄</span>
        <button onClick={onToggle} className="rounded-xl p-1.5 text-slate-500 hover:bg-slate-100" title="收合側欄">
          <MenuIcon />
        </button>
      </div>

      <div className="px-3 pb-1 pt-2">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-bold text-teal-700 transition hover:bg-teal-50"
        >
          <PlusIcon />
          建立健檢資料
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {profiles.length === 0 && (
          <p className="mt-8 text-center text-xs text-slate-400">目前沒有健檢紀錄</p>
        )}
        {profiles.map((profile) => {
          const isActive = profile.id === currentId;
          const showMenu = hoveredId === profile.id || isActive;

          return (
            <div
              key={profile.id}
              onClick={() => {
                if (renamingId !== profile.id) onSelect(profile.id);
              }}
              onMouseEnter={() => setHoveredId(profile.id)}
              onMouseLeave={() => setHoveredId(null)}
              className={`relative mt-1 flex cursor-pointer items-center rounded-xl px-3 py-2 text-sm transition ${
                isActive ? "bg-teal-50 text-teal-800" : "text-slate-700 hover:bg-slate-100"
              }`}
            >
              <div className="min-w-0 flex-1">
                {renamingId === profile.id ? (
                  <input
                    autoFocus
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    onBlur={commitRename}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") commitRename();
                      if (e.key === "Escape") setRenamingId(null);
                      e.stopPropagation();
                    }}
                    onClick={(e) => e.stopPropagation()}
                    className="w-full border-b border-teal-400 bg-transparent text-xs focus:outline-none"
                  />
                ) : (
                  <>
                    <span className="block truncate text-xs font-bold">{profile.name}</span>
                    <span className="text-xs text-slate-400">
                      {profile.members.length} / {profile.totalMembers} 人
                    </span>
                  </>
                )}
              </div>

              {showMenu && renamingId !== profile.id && (
                <div
                  className="relative ml-1 shrink-0"
                  ref={menuOpenId === profile.id ? menuRef : undefined}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => setMenuOpenId(menuOpenId === profile.id ? null : profile.id)}
                    className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600"
                    title="更多操作"
                  >
                    <DotsIcon />
                  </button>

                  {menuOpenId === profile.id && (
                    <div className="absolute right-0 top-full z-50 mt-1 w-36 rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
                      <button
                        onClick={() => {
                          setMenuOpenId(null);
                          setRenamingId(profile.id);
                          setRenameValue(profile.name);
                        }}
                        className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
                      >
                        <RenameIcon />
                        重新命名
                      </button>
                      <div className="my-1 border-t border-slate-100" />
                      <button
                        onClick={() => {
                          onDelete(profile.id);
                          setMenuOpenId(null);
                        }}
                        className="flex w-full items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50"
                      >
                        <TrashIcon />
                        刪除
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" />
      <line x1="3" y1="12" x2="21" y2="12" />
      <line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function DotsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="5" cy="12" r="2" />
      <circle cx="12" cy="12" r="2" />
      <circle cx="19" cy="12" r="2" />
    </svg>
  );
}

function RenameIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="3,6 5,6 21,6" />
      <path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6" />
      <path d="M8,6V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2" />
    </svg>
  );
}
