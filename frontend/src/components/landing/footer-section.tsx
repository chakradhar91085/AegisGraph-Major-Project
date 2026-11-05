export function FooterSection() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-slate-950 border-t border-slate-900 pt-16 pb-8">
      <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-12 lg:gap-8 mb-16">
          
          {/* Brand Column */}
          <div className="md:col-span-6 lg:col-span-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <div className="relative flex items-center justify-center w-6 h-6 text-blue-500">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <circle cx="12" cy="9" r="1.5" fill="currentColor" />
                  <circle cx="8.5" cy="14" r="1.5" fill="currentColor" />
                  <circle cx="15.5" cy="14" r="1.5" fill="currentColor" />
                  <path d="M12 9l-3.5 5M12 9l3.5 5M8.5 14h7" strokeWidth="1" strokeDasharray="1 2" opacity="0.8" />
                </svg>
              </div>
              <span className="font-sans font-semibold text-lg text-slate-50">AegisGraph</span>
            </div>
            <p className="text-slate-400 text-sm font-sans max-w-xs leading-relaxed">
              Behavioral Security for Graph-RAG.
            </p>
          </div>

          {/* Links Column 1: Platform */}
          <div className="md:col-span-3 lg:col-span-2 lg:col-start-8 flex flex-col gap-4">
            <h4 className="font-sans font-semibold text-slate-200 text-sm">
              Platform
            </h4>
            <nav className="flex flex-col gap-3">
              <a href="#overview" className="text-slate-400 hover:text-blue-400 text-sm font-sans transition-colors">
                Overview
              </a>
              <a href="#security" className="text-slate-400 hover:text-blue-400 text-sm font-sans transition-colors">
                Security
              </a>
              <a href="#architecture" className="text-slate-400 hover:text-blue-400 text-sm font-sans transition-colors">
                Architecture
              </a>
            </nav>
          </div>

          {/* Links Column 2: Project */}
          <div className="md:col-span-3 lg:col-span-2 flex flex-col gap-4">
            <h4 className="font-sans font-semibold text-slate-200 text-sm">
              Project
            </h4>
            <nav className="flex flex-col gap-3">
              <a href="https://github.com/chakradhar91085/AegisGraph-Core-Architecture" target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-blue-400 text-sm font-sans transition-colors">
                Source Code
              </a>
              <a href="https://github.com/chakradhar91085/AegisGraph-Core-Architecture/blob/master/backend/docs/AegisGraph_Technical_Architecture.md" target="_blank" rel="noopener noreferrer" className="text-slate-400 hover:text-blue-400 text-sm font-sans transition-colors">
                Documentation
              </a>
            </nav>
          </div>
        </div>

        {/* Bottom Bar */}
        <div className="pt-8 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-slate-500 text-sm font-sans text-center sm:text-left">
            AegisGraph Research Project
          </p>
          <p className="text-slate-500 text-sm font-sans text-center sm:text-right">
            &copy; {currentYear} AegisGraph. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
