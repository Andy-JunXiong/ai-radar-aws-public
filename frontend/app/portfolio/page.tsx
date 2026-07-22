import {
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  FileSearch,
  Radar,
  Route,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

import PortfolioCaseCard from "@/components/portfolio/PortfolioCaseCard";
import PortfolioEvidenceBoundary from "@/components/portfolio/PortfolioEvidenceBoundary";
import { portfolioCases } from "@/content/portfolio";

import styles from "./portfolio.module.css";

const liveProductUrl = "https://app.ai-radar-lab.com";
const githubUrl = "https://github.com/Andy-JunXiong/ai-radar-aws-public";
const linkedinUrl = "https://www.linkedin.com/in/jun-xiong-48123856/";
const publicRepoUrl = "https://github.com/Andy-JunXiong/ai-radar-aws-public/blob/main";

export const metadata = {
  title: "AI Radar Evidence Portfolio",
  description: "Evidence of governed AI product judgment, implementation, and evaluation.",
};

export default function PortfolioPage() {
  return (
    <div className={styles.page}>
      <section className={styles.hero}>
        <div>
          <p className={styles.eyebrow}>AI Radar Evidence Portfolio</p>
          <h1>Designing and building a governed AI system that makes evidence, constraints, and human judgment explicit.</h1>
          <p className={styles.heroCopy}>
            AI Radar is a live system I independently designed and built to turn fragmented AI signals
            into reviewable intelligence. This portfolio shows where governance judgments changed the
            implementation—and which claims the available evidence can and cannot support.
          </p>
          <div className={styles.heroActions}>
            <a className={styles.primaryButton} href="#case-studies"><FileSearch size={17} aria-hidden="true" />Explore the case studies</a>
            <a className={styles.secondaryButton} href={liveProductUrl} target="_blank" rel="noreferrer"><Radar size={17} aria-hidden="true" />View the live product</a>
          </div>
        </div>
        <aside className={styles.heroLedger} aria-label="Portfolio evidence index">
          <div className={styles.heroLedgerHeader}>
            <small>Evidence index</small>
            <strong>A compact map of what can be inspected.</strong>
          </div>
          <div className={styles.heroLedgerStats}>
            <div><b>03</b><span>Governance cases</span></div>
            <div><b>03</b><span>Public notebooks</span></div>
            <div><b>01</b><span>Live system</span></div>
          </div>
          <div className={styles.heroLedgerBoundary}>
            <ShieldCheck size={19} aria-hidden="true" />
            <p><strong>Evidence before assertion.</strong><span>Every case states what the available artifacts support—and where they stop.</span></p>
          </div>
          <a href="#case-studies">Open the evidence index <ArrowRight size={15} aria-hidden="true" /></a>
        </aside>
      </section>

      <section className={styles.productSection} aria-labelledby="product-title">
        <div className={styles.sectionIntro}>
          <p className={styles.eyebrow}>Live product and verified implementation trace</p>
          <h2 id="product-title">The product is deployed. This boundary is inspectable.</h2>
          <p>
            The live link proves that AI Radar is deployed. The trace below follows a real Project Takeaway
            request through the public route, source-aware policy, and tests that enforce the boundary.
          </p>
        </div>
        <div className={styles.productGrid}>
          <div className={styles.stagedSurface} aria-label="Verified Project Takeaway implementation trace">
            <div className={styles.stagedBar}>
              <strong>Ordinary Project Takeaway candidate creation</strong>
              <span>Code-traced · Test-supported</span>
            </div>
            <div className={styles.stagedBody}>
              <div>
                <small>Real enforced case</small>
                <h3>An unverified manual entry cannot enter the ordinary creation path.</h3>
                <p>Scope: ordinary Project Takeaway candidate creation only.</p>
              </div>
              <ol className={styles.traceSteps}>
                <li>
                  <span><Route size={17} aria-hidden="true" /></span>
                  <div><strong>Route receives candidate request</strong><small>projects.py</small></div>
                </li>
                <li>
                  <span><ShieldCheck size={17} aria-hidden="true" /></span>
                  <div><strong>Source-aware policy classifies eligibility</strong><small>project_takeaway_candidate_policy.py</small></div>
                </li>
                <li>
                  <span><ServerCog size={17} aria-hidden="true" /></span>
                  <div><strong>Policy failure returns HTTP 400</strong><small>Persistence is not called</small></div>
                </li>
                <li>
                  <span><CheckCircle2 size={17} aria-hidden="true" /></span>
                  <div><strong>Tests preserve the ordinary-path boundary</strong><small>Explicit override remains separate and audited</small></div>
                </li>
              </ol>
              <div className={styles.traceLinks}>
                <a href={`${publicRepoUrl}/backend/app/routes/projects.py`} target="_blank" rel="noreferrer">Inspect route</a>
                <a href={`${publicRepoUrl}/backend/app/services/project_takeaway_candidate_policy.py`} target="_blank" rel="noreferrer">Inspect policy</a>
                <a href={`${publicRepoUrl}/tests/test_project_takeaway_candidate_policy.py`} target="_blank" rel="noreferrer">Inspect tests</a>
              </div>
            </div>
          </div>
          <div className={styles.productProof}>
            <h3>What each artifact proves</h3>
            <dl>
              <div><dt>Live product</dt><dd>Deployment and accessible machinery</dd></div>
              <div><dt>Implementation trace</dt><dd>A narrow rule is enforced before persistence</dd></div>
              <div><dt>Tests</dt><dd>The ordinary path and explicit exception remain distinct</dd></div>
              <div><dt>Product outcome</dt><dd>Not claimed here; a real output still requires human approval for provenance, redaction, and publication scope</dd></div>
            </dl>
            <a href={liveProductUrl} target="_blank" rel="noreferrer">Open the deployed AI Radar <ArrowRight size={15} aria-hidden="true" /></a>
          </div>
        </div>
      </section>

      <section className={styles.spineSection} aria-labelledby="spine-title">
        <div className={styles.sectionIntro}>
          <p className={styles.eyebrow}>Governance narrative</p>
          <h2 id="spine-title">Three places where a governance system can fail</h2>
        </div>
        <ol className={styles.spine}>
          {portfolioCases.map((item) => (
            <li key={item.notebookNumber}>
              <span className={styles.spineIcon}>{item.stage === "Ingestion" ? <Radar size={19} aria-hidden="true" /> : item.stage === "Enforcement" ? <ShieldCheck size={19} aria-hidden="true" /> : <BookOpenCheck size={19} aria-hidden="true" />}</span>
              <em>{item.stage}</em>
              <strong>{item.stage === "Ingestion" ? "What may enter?" : item.stage === "Enforcement" ? "What actually binds?" : "What does approval prove?"}</strong>
              <small>Notebook #{item.notebookNumber}</small>
            </li>
          ))}
        </ol>
      </section>

      <section className={styles.caseSection} id="case-studies" aria-labelledby="cases-title">
        <div className={styles.sectionIntro}>
          <p className={styles.eyebrow}>Selected evidence</p>
          <h2 id="cases-title">Three judgments, traced to what can actually support them</h2>
          <p>Each case starts in plain language; the deeper reasoning and evidence boundary remain available for inspection.</p>
        </div>
        <div className={styles.caseGrid}>
          {portfolioCases.map((caseStudy) => <PortfolioCaseCard key={caseStudy.notebookNumber} caseStudy={caseStudy} />)}
        </div>
      </section>

      <PortfolioEvidenceBoundary />

      <section className={styles.contextSection} aria-labelledby="context-title">
        <div className={styles.sectionIntro}>
          <p className={styles.eyebrow}>Build and operating context</p>
          <h2 id="context-title">Built from judgment to operation</h2>
        </div>
        <div className={styles.contextGrid}>
          <Fact icon={Radar} title="Product" text="Signal, review, project-learning, and manual-intelligence workflows" />
          <Fact icon={ServerCog} title="Application" text="Next.js frontend and FastAPI backend" />
          <Fact icon={Route} title="Operations" text="AWS-hosted services with documented deployment boundaries" />
          <Fact icon={ShieldCheck} title="Governance" text="ADRs, explicit approval gates, candidate policies, and blocked actions" />
          <Fact icon={FileSearch} title="Evaluation" text="Claim verification, composition checks, review records, and calibration" />
        </div>
      </section>

      <section className={styles.finalCta}>
        <p className={styles.eyebrow}>Continue the inspection</p>
        <h2>Inspect the work, not just the description.</h2>
        <div className={styles.heroActions}>
          <a className={styles.primaryButton} href={liveProductUrl} target="_blank" rel="noreferrer">View live product</a>
          <a className={styles.secondaryButton} href={githubUrl} target="_blank" rel="noreferrer">Open GitHub</a>
          <a className={styles.secondaryButton} href="#case-studies">Read all three notebooks</a>
          <a className={styles.secondaryButton} href={linkedinUrl} target="_blank" rel="noreferrer">Connect on LinkedIn</a>
        </div>
      </section>
    </div>
  );
}

type IconComponent = typeof Radar;

function Fact({ icon: Icon, title, text }: { icon: IconComponent; title: string; text: string }) {
  return <div><span className={styles.factIcon}><Icon size={18} aria-hidden="true" /></span><strong>{title}</strong><span>{text}</span></div>;
}
