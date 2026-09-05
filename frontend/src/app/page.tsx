import Link from "next/link";
import {
  ArrowUpRight,
  Database,
  MessageSquare,
  ShieldCheck,
  ArrowRight,
  Check,
  Table2,
  Code2,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { MysqlLogo, PostgresLogo } from "@/components/db-logos";
export default function Home() {
  return (
    <div className="landing">
      <header className="site-header">
        <Brand />
        <nav>
          <a href="#how-it-works">How it works</a>
          <Link href="/workspace" className="button small">
            Open workspace <ArrowUpRight size={16} />
          </Link>
        </nav>
      </header>
      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="intro">
              <span className="status-dot" /> A little curiosity. A lot of
              answers.
            </div>
            <h1>
              Your data.
              <br />
              In your words.
            </h1>
            <p>
              Go from “I wonder” to “now I know.” Connect your database and ask
              a question. Rowan brings back the data, the SQL, and the story
              behind it.
            </p>
            <Link href="/workspace" className="button">
              Start exploring <ArrowRight size={18} />
            </Link>
            <div className="hero-note">
              No account needed. Just your database.
            </div>
          </div>
          <div className="preview">
            <div className="preview-top">
              <span>
                <Database size={15} /> storefront
              </span>
              <span className="badge">
                <span className="status-dot" />
                Connected
              </span>
            </div>
            <div className="preview-body">
              <div className="example-label">An example conversation</div>
              <div className="sample-question">
                Which products brought in the most revenue?
              </div>
              <div className="answer-heading">
                <span className="mini-mark">r.</span> Here’s your top five.
              </div>
              <p>
                The Everyday Tote leads the way, accounting for 34% of revenue
                across these products.
              </p>
              <div className="preview-tabs">
                <span>
                  <Table2 size={14} /> Results
                </span>
                <span>
                  <Code2 size={14} /> SQL
                </span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Revenue</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["Everyday Tote", "$24,850", "100%"],
                    ["Studio Mug", "$18,420", "74%"],
                    ["Linen Notebook", "$12,680", "51%"],
                    ["Desk Tray", "$9,540", "38%"],
                    ["Pocket Pen", "$7,260", "29%"],
                  ].map(([name, amount, width]) => (
                    <tr key={name}>
                      <td>{name}</td>
                      <td>{amount}</td>
                      <td>
                        <div className="bar" style={{ width }} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="preview-footer">
                <span>
                  <Check size={13} /> Read-only query
                </span>
                <span>5 rows returned</span>
              </div>
            </div>
            <div className="preview-caption">
              Real questions. Clear answers. SQL included.
            </div>
          </div>
        </section>
        <section className="compatibility">
          <span>At home with your database</span>
          <div>
            <PostgresLogo size={26} /> PostgreSQL
          </div>
          <div>
            <MysqlLogo size={26} /> MySQL
          </div>
        </section>
        <section id="how-it-works" className="how">
          <div className="section-heading">
            <h2>
              Less querying.
              <br />
              More understanding.
            </h2>
            <p>A simple path from your database to your next discovery.</p>
          </div>
          <div className="steps">
            {[
              {
                icon: Database,
                title: "Connect once",
                text: "Bring your PostgreSQL or MySQL database. Your workspace is ready without a sign-up.",
              },
              {
                icon: MessageSquare,
                title: "Ask naturally",
                text: "Explore trends, compare numbers, or dig into a detail. Follow up in the same conversation.",
              },
              {
                icon: ShieldCheck,
                title: "See the whole answer",
                text: "Inspect the results and SQL, with execution metrics and agent activity one click away.",
              },
            ].map(({ icon: Icon, title, text }) => (
              <article key={title}>
                <Icon size={23} />
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>
        <section className="closing">
          <div>
            <h2>There’s a question in your data.</h2>
            <p>Let’s find the answer.</p>
          </div>
          <Link href="/workspace" className="button">
            Open your workspace <ArrowRight size={18} />
          </Link>
        </section>
      </main>
      <footer>
        <Brand />
        <span>Made for curious minds. Built for clear answers.</span>
        <span>Read-only by design</span>
      </footer>
    </div>
  );
}
