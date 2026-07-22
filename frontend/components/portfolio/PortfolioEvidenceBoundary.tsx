import styles from "@/app/portfolio/portfolio.module.css";

export default function PortfolioEvidenceBoundary() {
  return (
    <section className={styles.boundarySection} id="evidence-boundary" aria-labelledby="boundary-title">
      <div>
        <p className={styles.eyebrow}>Evidence boundary</p>
        <h2 id="boundary-title">What this portfolio proves—and what it does not</h2>
        <p>
          AI Radar is a live, independently built system, not a multi-tenant enterprise deployment.
          It demonstrates end-to-end product, architecture, governance, and evaluation patterns under
          realistic operating constraints. Evidence is linked at the level available: public reasoning,
          curated code and ADRs, public implementation traces, and explicit validation records.
        </p>
      </div>
      <div className={styles.boundaryComparison} role="table" aria-label="Supported evidence and explicit non-claims">
        <div className={styles.boundaryComparisonHead} role="row">
          <h3 role="columnheader">Supported here</h3>
          <h3 role="columnheader">Not claimed</h3>
        </div>
        <div className={styles.boundaryComparisonRow} role="row">
          <p role="cell">A working cloud-hosted system exists.</p>
          <p role="cell">Enterprise production ownership or customer outcomes.</p>
        </div>
        <div className={styles.boundaryComparisonRow} role="row">
          <p role="cell">Selected governance claims trace to reviewable artifacts.</p>
          <p role="cell">External sources endorse AI Radar.</p>
        </div>
        <div className={styles.boundaryComparisonRow} role="row">
          <p role="cell">Advisory and unresolved evidence is labelled.</p>
          <p role="cell">Human approval automatically proves comprehension.</p>
        </div>
      </div>
    </section>
  );
}
