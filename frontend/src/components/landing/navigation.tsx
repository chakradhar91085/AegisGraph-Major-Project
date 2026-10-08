import { useState, useEffect } from "react";
import { Menu, X } from "lucide-react";
import { SignedIn, SignedOut, SignInButton, UserButton } from "@clerk/clerk-react";

const navLinks = [
  { name: "OVERVIEW",     href: "#overview" },
  { name: "ARCHITECTURE", href: "#architecture" },
  { name: "SECURITY",     href: "#security" },
];

export function Navigation() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 8);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <>
      <header
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
          scrolled ? "bg-slate-950/95 backdrop-blur-md border-b border-slate-900" : "bg-transparent border-b border-transparent"
        }`}
      >
        <div className="px-6 lg:px-12 h-16 flex items-center justify-between max-w-[1400px] mx-auto">
          {/* Logo */}
          <a href="#" className="flex items-center gap-3 group">
            <div className="relative flex items-center justify-center w-7 h-7 text-blue-500 transition-colors duration-300">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="w-full h-full">
                {/* Minimal shield outline */}
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                {/* Graph nodes inside */}
                <circle cx="12" cy="9" r="1.5" fill="currentColor" />
                <circle cx="8.5" cy="14" r="1.5" fill="currentColor" />
                <circle cx="15.5" cy="14" r="1.5" fill="currentColor" />
                {/* Graph edges */}
                <path d="M12 9l-3.5 5M12 9l3.5 5M8.5 14h7" strokeWidth="1" strokeDasharray="1 2" opacity="0.8" />
              </svg>
            </div>
            <span className="font-sans font-semibold text-xl tracking-widest text-slate-50">AEGISGRAPH</span>
            <span className="hidden lg:block font-mono text-[10px] text-slate-500 border-l border-slate-800 pl-3 ml-1 tracking-widest uppercase mt-1">
              Behavioral Security for Graph-RAG
            </span>
          </a>

          {/* Desktop links */}
          <nav className="hidden md:flex items-center gap-8">
            {navLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                className="font-mono text-xs tracking-wider text-slate-400 hover:text-blue-400 transition-colors duration-300"
              >
                {link.name}
              </a>
            ))}
          </nav>

          {/* CTA */}
          <div className="hidden md:flex items-center gap-6">
            <SignedOut>
              <SignInButton mode="modal" forceRedirectUrl="/app">
                <button className="font-mono text-xs tracking-wider text-slate-400 hover:text-slate-50 transition-colors duration-300 cursor-pointer">
                  SIGN IN
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <a
                href="/app"
                className="font-mono text-[11px] tracking-widest bg-blue-600 text-slate-50 px-5 h-9 flex items-center hover:bg-blue-500 transition-colors duration-300 font-semibold mr-2 rounded-sm"
              >
                LAUNCH AEGISGRAPH →
              </a>
              <UserButton afterSignOutUrl="/" />
            </SignedIn>
          </div>

          {/* Mobile burger */}
          <button
            onClick={() => setOpen(!open)}
            className="md:hidden text-slate-200 p-1"
            aria-label="Toggle menu"
          >
            {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>
      </header>

      {/* Mobile menu */}
      <div
        className={`fixed inset-0 z-40 bg-slate-950 flex flex-col transition-opacity duration-300 ${
          open ? "opacity-100 pointer-events-auto" : "opacity-0 pointer-events-none"
        }`}
        style={{ paddingTop: "64px" }}
      >
        <div className="border-t border-slate-900 flex flex-col">
          {navLinks.map((link, i) => (
            <a
              key={link.name}
              href={link.href}
              onClick={() => setOpen(false)}
              className={`border-b border-slate-900 px-8 py-6 font-sans text-2xl font-semibold tracking-wider text-slate-200 hover:text-blue-400 transition-all duration-300 flex items-center justify-between ${
                open ? "opacity-100 translate-x-0" : "opacity-0 -translate-x-4"
              }`}
              style={{ transitionDelay: open ? `${i * 60}ms` : "0ms" }}
            >
              {link.name}
            </a>
          ))}
          <div className="border-b border-slate-900 px-8 py-6">
            <SignedOut>
              <SignInButton mode="modal" forceRedirectUrl="/app">
                <button className="w-full text-left font-sans text-2xl font-semibold tracking-wider text-slate-200 hover:text-blue-400 transition-colors duration-300">
                  SIGN IN
                </button>
              </SignInButton>
            </SignedOut>
          </div>
        </div>
        
        <div className="mt-auto p-8 border-t border-slate-900 bg-slate-950">
          <SignedIn>
            <a
              href="/app"
              onClick={() => setOpen(false)}
              className="w-full block text-center font-mono text-sm tracking-widest bg-blue-600 text-slate-50 py-4 font-semibold rounded-sm"
            >
              LAUNCH AEGISGRAPH →
            </a>
          </SignedIn>
        </div>
      </div>
    </>
  );
}
