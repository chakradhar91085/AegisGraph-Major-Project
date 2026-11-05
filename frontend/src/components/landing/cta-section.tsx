import { SignedIn, SignedOut, SignInButton } from "@clerk/clerk-react";
import { ShieldCheck } from "lucide-react";

export function CtaSection() {
  return (
    <section className="py-24 bg-slate-950 relative border-t border-slate-900">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 relative z-10">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-10 md:p-16 text-center max-w-4xl mx-auto flex flex-col items-center">
          
          <div className="mb-6">
            <ShieldCheck className="w-12 h-12 text-blue-500" />
          </div>
          
          <h2 className="font-sans font-semibold text-3xl md:text-4xl text-slate-50 mb-4 tracking-tight">
            EXPLORE BEHAVIORAL SECURITY FOR GRAPH-RAG
          </h2>
          
          <p className="text-slate-400 text-lg leading-relaxed font-sans mb-10 max-w-2xl">
            See how AegisGraph protects enterprise knowledge by monitoring interaction patterns and controlling retrieval dynamically.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 w-full justify-center">
            <SignedOut>
              <SignInButton mode="modal" forceRedirectUrl="/app">
                <button className="inline-flex items-center justify-center gap-2 bg-blue-600 text-white font-sans text-sm px-6 py-3.5 hover:bg-blue-500 transition-colors font-semibold rounded-sm">
                  Open AegisGraph
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <a
                href="/app"
                className="inline-flex items-center justify-center gap-2 bg-blue-600 text-white font-sans text-sm px-6 py-3.5 hover:bg-blue-500 transition-colors font-semibold rounded-sm"
              >
                Open AegisGraph
              </a>
            </SignedIn>
            <a
              href="#architecture"
              className="inline-flex items-center justify-center gap-2 border border-slate-700 text-slate-300 font-sans text-sm px-6 py-3.5 hover:bg-slate-800 hover:text-slate-50 transition-colors rounded-sm"
            >
              View Architecture
            </a>
          </div>

        </div>
      </div>
    </section>
  );
}
