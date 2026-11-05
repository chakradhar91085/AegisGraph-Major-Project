import { Navigation } from '../components/landing/navigation';
import { HeroSection } from '../components/landing/hero-section';
import { FeaturesSection } from '../components/landing/features-section';
import { HowItWorksSection } from '../components/landing/how-it-works-section';
import { SecuritySection } from '../components/landing/security-section';
import { ArchitectureSection } from '../components/landing/architecture-section';
import { CtaSection } from '../components/landing/cta-section';
import { FooterSection } from '../components/landing/footer-section';

export function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-x-hidden bg-slate-950">
      <Navigation />
      <HeroSection />
      <HowItWorksSection />
      <FeaturesSection />
      <SecuritySection />
      <ArchitectureSection />
      <CtaSection />
      <FooterSection />
    </main>
  );
}
