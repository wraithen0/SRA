import { Search, BarChart3, ListChecks } from "lucide-react";

const STEPS = [
  {
    icon: Search,
    title: "Pick your profile",
    detail: "Choose who you are. Every search is ranked for one of three underserved student profiles."
  },
  {
    icon: BarChart3,
    title: "Read the ranked evidence",
    detail: "Each match shows its score, the reasons behind it, official links, and deadlines."
  },
  {
    icon: ListChecks,
    title: "Follow the playbook",
    detail: "A step-by-step plan from application-fee waiver to FAFSA filing — plus the gaps we could not verify."
  }
];

const TRUST = ["Cache-first, from verified sources", "Official links only", "Gaps always shown"];

export function HowItWorks() {
  return (
    <section className="section how-it-works" aria-labelledby="how-heading">
      <h2 className="section__title" id="how-heading">
        How it works
      </h2>
      <ol className="how-steps">
        {STEPS.map((step) => {
          const Icon = step.icon;
          return (
            <li key={step.title} className="how-step">
              <Icon size={20} aria-hidden="true" />
              <h3>{step.title}</h3>
              <p>{step.detail}</p>
            </li>
          );
        })}
      </ol>
      <p className="trust-strip" role="note">
        {TRUST.join(" · ")}
      </p>
    </section>
  );
}
