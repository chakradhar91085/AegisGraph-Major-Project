export function HowItWorksSection() {
  const steps = [
    {
      num: "01",
      title: "OBSERVE",
      desc: "Monitor behavioral signals from the user's interaction with the system.",
    },
    {
      num: "02",
      title: "ASSESS",
      desc: "Combine behavioral signals and maintain session-level risk using EWMA.",
    },
    {
      num: "03",
      title: "ADAPT",
      desc: "Adjust retrieval policy based on behavioral risk.",
    },
    {
      num: "04",
      title: "RETRIEVE",
      desc: "Perform controlled Graph-RAG retrieval from the knowledge graph.",
    },
    {
      num: "05",
      title: "RESPOND",
      desc: "Generate a grounded response using the permitted retrieved context.",
    },
  ];

  return (
    <section className="py-24 bg-slate-950 relative border-t border-slate-900">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12 relative z-10">
        <div className="mb-16">
          <h2 className="font-sans font-semibold text-3xl md:text-4xl text-slate-50 mb-4 tracking-tight">
            How AegisGraph Works
          </h2>
          <p className="text-slate-400 text-lg leading-relaxed max-w-2xl font-sans">
            AegisGraph intercepts every interaction to enforce security dynamically.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {steps.map((step) => (
            <div
              key={step.num}
              className="bg-slate-900 border border-slate-800 p-6 rounded relative flex flex-col group hover:border-slate-700 transition-colors"
            >
              <div className="font-mono text-xs text-slate-500 mb-4">
                {step.num}
              </div>
              <h3 className="font-sans font-semibold text-sm text-slate-200 mb-3 tracking-wide">
                {step.title}
              </h3>
              <p className="text-slate-400 text-sm leading-relaxed mt-auto">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
