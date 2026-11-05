import { ArrowRight, ShieldCheck, ShieldAlert } from "lucide-react";

export function SecuritySection() {
  return (
    <section className="py-24 bg-slate-950 relative border-t border-slate-900" id="security">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 relative z-10">
        
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="font-sans font-semibold text-3xl md:text-4xl text-slate-50 mb-4 tracking-tight">
            Security That Adapts to Behavior
          </h2>
          <p className="text-slate-400 text-lg leading-relaxed font-sans">
            AegisGraph dynamically adjusts its retrieval constraints based on the ongoing behavioral risk assessment of the session.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          
          {/* Normal Behavior Path */}
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-lg flex flex-col items-center text-center">
            <div className="w-12 h-12 bg-emerald-950/30 border border-emerald-900/50 rounded-full flex items-center justify-center mb-6">
              <ShieldCheck className="w-6 h-6 text-emerald-500" />
            </div>
            <h3 className="font-sans font-semibold text-xl text-slate-200 mb-6">
              Normal Behavior
            </h3>
            
            <div className="flex flex-col items-center gap-3 w-full">
              <div className="bg-slate-950 border border-slate-800 py-3 w-full rounded text-sm text-slate-300 font-mono">
                Normal Interactions
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
              <div className="bg-slate-950 border border-slate-800 py-3 w-full rounded text-sm text-slate-300 font-mono">
                Lower Session Risk
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
              <div className="bg-emerald-950/20 border border-emerald-900/40 py-3 w-full rounded text-sm text-emerald-400 font-mono">
                Broader Retrieval
              </div>
            </div>
          </div>

          {/* Suspicious Behavior Path */}
          <div className="bg-slate-900 border border-slate-800 p-8 rounded-lg flex flex-col items-center text-center">
            <div className="w-12 h-12 bg-red-950/30 border border-red-900/50 rounded-full flex items-center justify-center mb-6">
              <ShieldAlert className="w-6 h-6 text-red-400" />
            </div>
            <h3 className="font-sans font-semibold text-xl text-slate-200 mb-6">
              Suspicious Behavior
            </h3>
            
            <div className="flex flex-col items-center gap-3 w-full">
              <div className="bg-slate-950 border border-slate-800 py-3 w-full rounded text-sm text-slate-300 font-mono">
                Suspicious Patterns
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
              <div className="bg-slate-950 border border-slate-800 py-3 w-full rounded text-sm text-slate-300 font-mono">
                Higher Session Risk
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
              <div className="bg-slate-950 border border-slate-800 py-3 w-full rounded text-sm text-slate-300 font-mono">
                Restricted Retrieval
              </div>
              <ArrowRight className="w-4 h-4 text-slate-600 rotate-90" />
              <div className="bg-red-950 border border-red-900 py-3 w-full rounded text-sm text-red-400 font-mono">
                Reduced Exposure
              </div>
            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
