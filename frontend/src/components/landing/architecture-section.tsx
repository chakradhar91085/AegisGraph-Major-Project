export function ArchitectureSection() {
  return (
    <section className="py-24 bg-slate-950 relative border-t border-slate-900">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 relative z-10">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="font-sans font-semibold text-3xl md:text-4xl text-slate-50 mb-4 tracking-tight">
            System Architecture
          </h2>
          <p className="text-slate-400 text-lg leading-relaxed font-sans">
            AegisGraph acts as a behavioral security layer sitting between the API gateway and the core Graph-RAG retrieval components.
          </p>
        </div>

        <div className="max-w-2xl mx-auto font-mono text-sm">
          <div className="flex flex-col items-center">
            
            {/* User */}
            <div className="bg-slate-900 border border-slate-800 text-slate-300 px-6 py-3 rounded text-center min-w-[240px]">
              User Request
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* FastAPI */}
            <div className="bg-slate-900 border border-slate-800 text-slate-300 px-6 py-3 rounded text-center min-w-[240px]">
              FastAPI
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* AegisGraph Security Layer */}
            <div className="bg-slate-950 border border-blue-900/50 p-6 rounded w-full">
              <div className="text-blue-500 font-semibold text-center mb-6 text-base">AegisGraph SECURITY LAYER</div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 p-4 rounded text-center text-slate-400 text-xs flex items-center justify-center">
                  Behavioral Telemetry
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded text-center text-slate-400 text-xs flex items-center justify-center">
                  Risk Engine / EWMA
                </div>
                <div className="bg-slate-900 border border-slate-800 p-4 rounded text-center text-slate-400 text-xs flex items-center justify-center">
                  Adaptive Policy
                </div>
              </div>
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* Controlled Graph-RAG Retrieval */}
            <div className="bg-slate-900 border border-slate-800 text-slate-300 px-6 py-3 rounded text-center min-w-[240px]">
              Controlled Graph-RAG Retrieval
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* Neo4j */}
            <div className="bg-slate-900 border border-slate-800 text-slate-300 px-6 py-3 rounded text-center min-w-[240px]">
              Neo4j
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* Local LLM */}
            <div className="bg-slate-900 border border-slate-800 text-slate-300 px-6 py-3 rounded text-center min-w-[240px]">
              Local LLM
            </div>
            <div className="h-8 border-l border-slate-800"></div>

            {/* Grounded Response */}
            <div className="bg-slate-900 border border-emerald-900/30 text-emerald-500 px-6 py-3 rounded text-center min-w-[240px]">
              Grounded Response
            </div>
            
          </div>
        </div>
      </div>
    </section>
  );
}
