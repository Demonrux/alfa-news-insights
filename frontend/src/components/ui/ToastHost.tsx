"use client";

import { useSession } from "@/lib/session";

export function ToastHost() {
  const { toasts, dismissToast } = useSession();
  return (
    <div className="toast-host" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast" role="status">
          <span>{t.text}</span>
          {t.action ? (
            <button
              type="button"
              className="toast-act"
              onClick={() => {
                t.action?.run();
                dismissToast(t.id);
              }}
            >
              {t.action.label}
            </button>
          ) : null}
        </div>
      ))}
    </div>
  );
}
