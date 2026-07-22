import { BookOpenCheck, Radar, ShieldCheck } from "lucide-react";

import type { PortfolioCaseStudy } from "@/content/portfolio";

import styles from "@/app/portfolio/portfolio.module.css";

export default function PortfolioCaseCard({ caseStudy }: { caseStudy: PortfolioCaseStudy }) {
  const StageIcon = caseStudy.stage === "Ingestion" ? Radar : caseStudy.stage === "Enforcement" ? ShieldCheck : BookOpenCheck;
  return (
    <article className={styles.caseCard}>
      <div className={styles.caseMeta}>
        <span>Notebook #{caseStudy.notebookNumber}</span>
        <span><StageIcon size={14} aria-hidden="true" />{caseStudy.stage}</span>
      </div>
      <h3>{caseStudy.title}</h3>
      <p className={styles.skimmer}>{caseStudy.skimmer}</p>
      <div className={styles.capabilityList} aria-label="Relevant capabilities">
        {caseStudy.capabilities.map((capability) => (
          <span key={capability}>{capability}</span>
        ))}
      </div>
      <p>{caseStudy.summary}</p>
      {caseStudy.notebookNumber === 6 ? <EnforcementLadder /> : null}
      {caseStudy.notebookNumber === 5 ? <BorrowedShells /> : null}
      {caseStudy.notebookNumber === 9 ? <ProxyGap /> : null}
      <div className={styles.provenanceRow}>
        <strong>Evidence tier</strong>
        <span>{caseStudy.provenance}</span>
      </div>
      <p className={styles.caveat}><strong>Boundary:</strong> {caseStudy.caveat}</p>
      <div className={styles.evidenceLinks}>
        <a href={caseStudy.primaryEvidence.href} target="_blank" rel="noreferrer">
          {caseStudy.primaryEvidence.label}
        </a>
        <details>
          <summary>Inspect supporting evidence</summary>
          <ul>
            {caseStudy.supportingEvidence.map((link) => (
              <li key={link.href}>
                <a href={link.href} target="_blank" rel="noreferrer">{link.label}</a>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </article>
  );
}

function EnforcementLadder() {
  return (
    <div className={styles.miniDiagram} aria-label="Constraint strength rises from documented to sandboxed">
      {['Documented', 'Reviewed', 'Constructed', 'Sandboxed'].map((label, index) => (
        <div key={label}><span>{index + 1}</span><strong>{label}</strong></div>
      ))}
    </div>
  );
}

function BorrowedShells() {
  return (
    <div className={styles.equationDiagram} aria-label="Three evidence distinctions">
      <span>Relevance ≠ admission</span>
      <span>Overlap ≠ provenance</span>
      <span>Symptom ≠ diagnosis</span>
    </div>
  );
}

function ProxyGap() {
  return (
    <div className={styles.proxyDiagram} aria-label="A green proxy does not prove comprehension">
      <span>Green quiz</span><span aria-hidden="true">→</span><span>Reported comprehension</span>
      <span>Green quiz</span><span aria-hidden="true">↛</span><strong>Demonstrated comprehension</strong>
    </div>
  );
}
