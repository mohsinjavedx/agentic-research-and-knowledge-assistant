"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

export function ModalDialog({
  open,
  title,
  children,
  onClose,
  className = "",
}: {
  open: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (!open) return;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const element = ref.current;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    element?.showModal();
    return () => {
      element?.close();
      document.body.style.overflow = overflow;
      if (trigger?.isConnected) trigger.focus();
      else {
        const heading = document.querySelector<HTMLElement>("#main h1");
        heading?.setAttribute("tabindex", "-1");
        heading?.focus();
      }
    };
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`modal-dialog ${className}`}
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        if (
          event.target === event.currentTarget &&
          (event.clientX < rect.left ||
            event.clientX > rect.right ||
            event.clientY < rect.top ||
            event.clientY > rect.bottom)
        )
          onClose();
      }}
    >
      <header className="modal-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label={`Close ${title.toLowerCase()}`}
          onClick={onClose}
        >
          <X size={18} />
        </button>
      </header>
      {open && children}
    </dialog>
  );
}
