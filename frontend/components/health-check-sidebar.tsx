"use client";

import { useState, useRef, useEffect } from "react";
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
  profiles, currentId, open, onNew, onSelect, onDelete, onRename, onToggle,
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
      <div className="flex flex-col w-12 shrink-0 border-r border-gray-200 bg-white items-center py-3 gap-2">
        <button onClick={onToggle} className="p-2 rounded-lg hover:bg-gray-100 text-gray-500">
          <MenuIcon />
        </button>
        <button onClick={onNew} className="p-2 rounded-lg hover:bg-blue-50 text-blue-700">
          <PlusIcon />
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-64 shrink-0 border-r border-gray-200 bg-white overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <span className="font-semibold text-sm text-gray-700">顧客資料</span>
        <button onClick={onToggle} className="p-1.5 rounded-lg hover:bg-gray-100 text-gray-500">
          <MenuIcon />
        </button>
      </div>

      <div className="px-3 pt-2 pb-1">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium text-blue-700 hover:bg-blue-50 transition-colors"
        >
          <PlusIcon />
          建立資料
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-4">
        {profiles.length === 0 && (
          <p className="text-xs text-gray-400 text-center mt-8">尚無顧客資料</p>
        )}
        {profiles.map((profile) => {
          const isActive = profile.id === currentId;
          const showMenu = hoveredId === profile.id || isActive;

          return (
            <div
              key={profile.id}
              onClick={() => { if (renamingId !== profile.id) onSelect(profile.id); }}
              onMouseEnter={() => setHoveredId(profile.id)}
              onMouseLeave={() => setHoveredId(null)}
              className={`relative flex items-center rounded-lg px-3 py-2 mt-1 text-sm cursor-pointer transition-colors ${
                isActive ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-100"
              }`}
            >
              <div className="flex-1 min-w-0">
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
                    className="w-full text-xs bg-transparent border-b border-blue-400 focus:outline-none"
                  />
                ) : (
                  <>
                    <span className="truncate text-xs font-medium block">{profile.name}</span>
                    <span className="text-xs text-gray-400">
                      {profile.members.length} / {profile.totalMembers} 人
                    </span>
                  </>
                )}
              </div>

              {showMenu && renamingId !== profile.id && (
                <div
                  className="relative shrink-0 ml-1"
                  ref={menuOpenId === profile.id ? menuRef : undefined}
                  onClick={(e) => e.stopPropagation()}
                >
                  <button
                    onClick={() => setMenuOpenId(menuOpenId === profile.id ? null : profile.id)}
                    className="p-1 rounded hover:bg-gray-200 text-gray-400 hover:text-gray-600"
                  >
                    <DotsIcon />
                  </button>

                  {menuOpenId === profile.id && (
                    <div className="absolute right-0 top-full mt-1 w-36 bg-white border border-gray-200 rounded-xl shadow-lg z-50 py-1">
                      <button
                        onClick={() => {
                          setMenuOpenId(null);
                          setRenamingId(profile.id);
                          setRenameValue(profile.name);
                        }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
                      >
                        <RenameIcon />
                        重新命名
                      </button>
                      <div className="border-t border-gray-100 my-1" />
                      <button
                        onClick={() => { onDelete(profile.id); setMenuOpenId(null); }}
                        className="w-full flex items-center gap-2.5 px-3 py-2 text-sm text-red-500 hover:bg-red-50"
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
    </div>
  );
}

function MenuIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  );
}
function PlusIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}
function DotsIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="5" cy="12" r="2" /><circle cx="12" cy="12" r="2" /><circle cx="19" cy="12" r="2" />
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
