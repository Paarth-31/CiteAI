"use client";

import { useEffect, useRef } from "react";

type ReporterProps = {
  error?: Error & { digest?: string };
  reset?: () => void;
};

export default function ErrorReporter({ error, reset }: ReporterProps) {
  const lastOverlayMsg = useRef("");
  const pollRef = useRef<NodeJS.Timeout>();

  useEffect(() => {
    const inIframe = window.parent !== window;
    if (!inIframe) return;

    const send = (payload: unknown) => window.parent.postMessage(payload, "*");

    const onError = (e: ErrorEvent) =>
      send({
        type: "ERROR_CAPTURED",
        error: {
          message: e.message,
          stack: e.error?.stack,
          filename: e.filename,
          lineno: e.lineno,
          colno: e.colno,
          source: "window.onerror",
        },
        timestamp: Date.now(),
      });

    const onReject = (e: PromiseRejectionEvent) =>
      send({
        type: "ERROR_CAPTURED",
        error: {
          message: e.reason?.message ?? String(e.reason),
          stack: e.reason?.stack,
          source: "unhandledrejection",
        },
        timestamp: Date.now(),
      });

    const pollOverlay = () => {
      const overlay = document.querySelector("[data-nextjs-dialog-overlay]");
      const node =
        overlay?.querySelector(
          "h1, h2, .error-message, [data-nextjs-dialog-body]"
        ) ?? null;
      const txt = node?.textContent ?? node?.innerHTML ?? "";
      if (txt && txt !== lastOverlayMsg.current) {
        lastOverlayMsg.current = txt;
        send({
          type: "ERROR_CAPTURED",
          error: { message: txt, source: "nextjs-dev-overlay" },
          timestamp: Date.now(),
        });
      }
    };

    window.addEventListener("error", onError);
    window.addEventListener("unhandledrejection", onReject);
    pollRef.current = setInterval(pollOverlay, 1000);

    return () => {
      window.removeEventListener("error", onError);
      window.removeEventListener("unhandledrejection", onReject);
      pollRef.current && clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (!error) return;
    window.parent.postMessage(
      {
        type: "global-error-reset",
        error: {
          message: error.message,
          stack: error.stack,
          digest: error.digest,
          name: error.name,
        },
        timestamp: Date.now(),
        userAgent: navigator.userAgent,
      },
      "*"
    );
  }, [error]);

  if (!error) return null;

  return (
    <html>
      <body className="min-h-screen bg-[#0f1117] text-[#f0f4f8] flex items-center justify-center p-4 font-[var(--font-sans)]">
        <div className="max-w-xl w-full text-center space-y-8 glass-card rounded-3xl p-10">
          <div className="space-y-3">
            <div className="w-20 h-20 bg-[#f43f5e]/10 border border-[#f43f5e]/30 rounded-full flex items-center justify-center mx-auto mb-6 shadow-[0_0_20px_rgba(244,63,94,0.15)]">
               <span className="text-4xl text-[#f43f5e] font-bold font-[var(--font-mono)]">!</span>
            </div>
            <h1 className="text-3xl font-bold text-[#f43f5e] font-[var(--font-heading)] tracking-tight">
              System Fault Detected
            </h1>
            <p className="text-[#c9d1dc] text-lg">
              An unexpected process disruption occurred. 
            </p>
          </div>
          
          <div className="space-y-4">
            {process.env.NODE_ENV === "development" && (
              <details className="mt-6 text-left group">
                <summary className="cursor-pointer text-sm font-bold font-[var(--font-mono)] uppercase tracking-widest text-[#6b7a8d] hover:text-[#f0f4f8] transition-colors p-3 bg-[#161b25] border border-[#242c3a] rounded-xl outline-none list-none text-center">
                  View Technical Diagnostics
                </summary>
                <pre className="mt-4 text-[11px] bg-[#050a0e] text-[#29b6f6] border border-[#242c3a] p-4 rounded-xl overflow-auto font-[var(--font-mono)] leading-relaxed max-h-[300px] shadow-inner custom-scrollbar">
                  <span className="text-[#f43f5e] font-bold block mb-2">{error.message}</span>
                  {error.stack && (
                    <div className="mt-2 opacity-80">
                      {error.stack}
                    </div>
                  )}
                  {error.digest && (
                    <div className="mt-4 text-[#f0f4f8] bg-[#1e2433] p-2 rounded block">
                      Digest Hash: {error.digest}
                    </div>
                  )}
                </pre>
              </details>
            )}
            
            {reset && (
              <button onClick={reset} className="btn-secondary mt-6 mx-auto">
                Reinitialize Sequence
              </button>
            )}
          </div>
        </div>
      </body>
    </html>
  );
}