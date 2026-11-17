"use client";

import { AlertTriangle, CheckCircle2, GitBranch, Layers, Ruler, ShieldAlert, XCircle } from "lucide-react";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { CountUp } from "@/components/ui/count-up";
import { Badge, EmptyState, ErrorState, InfoTip, Metric, Notice, Panel, PanelHeader, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/primitives";
import { axisLabel, axisProps, ChartInView, ChartTooltip, gridProps, useChartMotion } from "@/components/viz/chart-kit";
import { useApi } from "@/lib/api";
import { clusterColor } from "@/lib/palette";
import { num } from "@/lib/utils";
import type { Modelling, ModelRow } from "@/types/api";

/* ------------------------------------------------------------------ development */

function Development({ m }: { m: Modelling }) {
  const d = m.dataset;
  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
      <Panel>
        <PanelHeader eyebrow="Model development" title="Target, features and labels" description="Why this is the only supervised question the data supports." />
        <dl className="flex flex-col gap-4 p-5">
          <div>
            <dt className="text-sm font-medium">Prediction target</dt>
            <dd className="mt-1 text-[13px] leading-relaxed text-muted">
              <b className="text-ink/90">{m.target.label}.</b> {m.target.definition}
            </dd>
          </div>
          <div>
            <dt className="text-sm font-medium">Why this target</dt>
            <dd className="mt-1 text-[13px] leading-relaxed text-muted">{m.target.why}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium">Sequence features</dt>
            <dd className="mt-1 text-[13px] leading-relaxed text-muted">{m.target.features}</dd>
          </div>
          <div>
            <dt className="text-sm font-medium">Algorithms evaluated</dt>
            <dd className="mt-1 text-[13px] leading-relaxed text-muted">
              Logistic regression (L2, C = 0.1) and a random forest (300 trees, minimum leaf 3) on the feature table, plus a similarity-weighted 5-nearest-neighbour
              model that transfers labels along alignment identity. Hyperparameters were fixed in advance rather than tuned, because the sample is too small for
              a nested search to mean anything.
            </dd>
          </div>
        </dl>
      </Panel>

      <Panel>
        <PanelHeader eyebrow="Training data" title="Class distribution" description="Proteins from the standardised screen with a usable label." />
        {!d ? (
          <div className="p-5">
            <EmptyState variant="unavailable" title="Prediction dataset not generated" />
          </div>
        ) : (
          <div className="flex flex-col gap-5 p-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Metric label="Proteins" value={<CountUp id="validation:proteins" value={d.n_proteins} format={num} />} />
              <Metric label="Detected" value={<CountUp id="validation:positive" value={d.n_positive} format={num} />} accent="var(--color-mint)" />
              <Metric label="Not detected" value={<CountUp id="validation:negative" value={d.n_negative} format={num} />} accent="var(--color-rose)" />
              <Metric label="Identity groups" value={<CountUp id="validation:groups" value={d.n_identity_groups} format={num} />} accent="var(--color-amber)" hint="at 70% identity" />
            </div>
            <div>
              <div className="eyebrow mb-2">Balance</div>
              <div className="grow-x flex h-3 overflow-hidden rounded-full">
                <div className="bg-mint" style={{ width: `${(100 * d.n_positive) / d.n_proteins}%` }} />
                <div className="bg-rose" style={{ width: `${(100 * d.n_negative) / d.n_proteins}%` }} />
              </div>
              <p className="mt-2 text-xs text-muted">
                The classes are balanced by construction, so a majority-class baseline scores 0.5 and any score above that has to be earned.
              </p>
            </div>
            <div>
              <div className="eyebrow mb-2">By sequence subgroup</div>
              <div className="flex flex-col gap-2">
                {d.by_subcluster.map((s) => (
                  <div key={s.subcluster} className="grid grid-cols-[auto_1fr_auto] items-center gap-3 text-xs">
                    <span className="font-mono" style={{ color: clusterColor(s.subcluster) }}>
                      {s.subcluster}
                    </span>
                    <div className="h-2 overflow-hidden rounded-full bg-rose/30">
                      <div className="grow-x h-full rounded-full bg-mint" style={{ width: `${(100 * s.positive) / s.n}%` }} />
                    </div>
                    <span className="tabular font-mono text-muted">
                      {s.positive}/{s.n} detected
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ splitting */

function Splitting({ m }: { m: Modelling }) {
  const d = m.dataset;
  const largest = d?.group_sizes[0] ?? 0;
  return (
    <Panel>
      <PanelHeader
        eyebrow="Training and testing strategy"
        title="Homology-aware cross-validation"
        description={m.target.splitting}
        action={<GitBranch className="size-4 text-muted" />}
      />
      <div className="grid gap-5 p-5 lg:grid-cols-[1fr_1.1fr]">
        <div className="stagger flex flex-col gap-3">
          {[
            ["Grouping", "Proteins are grouped at 70% sequence identity before any split. Every member of a group lands in the same fold."],
            ["Partitioning", "5-fold StratifiedGroupKFold keeps the class balance in each fold while respecting those groups."],
            ["Repetition", "The whole procedure repeats 20 times with different seeds; reported scores are means across all folds and repeats."],
            ["Degenerate folds", "A fold whose test set contains only one class is skipped rather than scored, because ROC AUC is undefined there."],
            ["Duplicate control", "The curated set contains no duplicate sequences (QC check), so no protein can appear twice."],
          ].map(([t, text]) => (
            <div key={t} className="hover-card rounded-lg border border-line/70 bg-void/40 p-3">
              <div className="text-[13px] font-medium">{t}</div>
              <p className="mt-1 text-xs leading-relaxed text-muted">{text}</p>
            </div>
          ))}
        </div>

        <div className="rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-3">Homology group sizes</div>
          {!d ? (
            <Skeleton label="Loading homology groups" className="h-40" />
          ) : (
            <>
              <div className="flex flex-wrap gap-1.5">
                {d.group_sizes.map((n, i) => (
                  <span
                    key={i}
                    title={`${n} protein${n === 1 ? "" : "s"}`}
                    className="grid place-items-center rounded-md border font-mono text-[11px]"
                    style={{
                      width: `${Math.max(26, Math.min(64, 22 + n * 1.3))}px`,
                      height: "26px",
                      borderColor: n > 5 ? "color-mix(in srgb, var(--color-amber) 40%, transparent)" : "color-mix(in srgb, var(--color-line) 60%, transparent)",
                      background: n > 5 ? "color-mix(in srgb, var(--color-amber) 8%, transparent)" : "var(--color-elevated)",
                      color: n > 5 ? "var(--color-amber)" : "var(--color-muted)",
                    }}
                  >
                    {n}
                  </span>
                ))}
              </div>
              <Notice tone="warn" className="mt-4">
                {num(d.n_proteins)} proteins fall into only {d.n_identity_groups} independent groups, and the largest group alone holds {largest} of them.
                Grouped splitting is what keeps the evaluation honest — and it is also why the effective sample size is small enough that scores are unstable.
              </Notice>
            </>
          )}
        </div>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ comparison */

function Comparison({ rows }: { rows: ModelRow[] }) {
  const data = useMemo(() => [...rows].sort((a, b) => a.roc_auc_mean - b.roc_auc_mean).map((r) => ({ ...r, err: r.roc_auc_sd })), [rows]);
  const motion = useChartMotion(data, 750);

  return (
    <Panel>
      <PanelHeader
        eyebrow="Model comparison"
        title="Out-of-fold ROC AUC against baselines"
        description="Bars are means over 20 repeats of 5-fold grouped cross-validation; whiskers are one standard deviation across folds. 0.5 is chance."
        action={<InfoTip content="A baseline is a deliberately uninformative predictor. If a model cannot beat the majority class and random scores, its features carry no usable signal." />}
      />
      <div className="p-5">
        <ChartInView className="chart-hl h-[320px]">
          <ResponsiveContainer>
            <BarChart data={data} layout="vertical" margin={{ top: 4, right: 32, bottom: 20, left: 150 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis
                type="number"
                domain={[0.3, 0.8]}
                ticks={[0.3, 0.4, 0.5, 0.6, 0.7, 0.8]}
                {...axisProps}
                label={{ value: "ROC AUC (out-of-fold mean)", position: "bottom", fill: "var(--color-muted)", fontSize: 11, offset: 0 }}
              />
              <YAxis type="category" dataKey="model" width={150} {...axisProps} />
              <ReferenceLine x={0.5} stroke="var(--color-rose)" strokeDasharray="4 4" label={{ value: "chance", fill: "var(--color-rose)", fontSize: 10, position: "top" }} />
              <Tooltip
                cursor={{ fill: "var(--chart-cursor)" }}
                content={({ payload }) => {
                  const r = payload?.[0]?.payload as (typeof data)[number] | undefined;
                  return r ? (
                    <ChartTooltip
                      title={r.model}
                      rows={[
                        { label: "ROC AUC", value: `${r.roc_auc_mean.toFixed(3)} ± ${r.roc_auc_sd.toFixed(3)}`, color: r.kind === "model" ? "var(--color-aqua)" : "var(--color-slate)" },
                        { label: "Balanced accuracy", value: `${r.balanced_accuracy_mean.toFixed(3)} ± ${r.balanced_accuracy_sd.toFixed(3)}` },
                        { label: "Kind", value: r.kind },
                      ]}
                    />
                  ) : null;
                }}
              />
              <Bar dataKey="roc_auc_mean" radius={[0, 4, 4, 0]} {...motion}>
                {data.map((r) => (
                  <Cell key={r.model} fill={r.kind === "model" ? "var(--color-aqua)" : "var(--color-slate)"} />
                ))}
                <ErrorBar dataKey="err" width={4} strokeWidth={1.5} stroke="var(--color-muted)" direction="x" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartInView>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm bg-teal" /> Models
          </span>
          <span className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-sm" style={{ background: "var(--color-slate)" }} /> Baselines
          </span>
        </div>
        <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted">
          Every model sits within one standard deviation of chance. The spread across folds is larger than the gap between the best model and the baselines,
          which is the signature of a dataset with too few independent sequence groups rather than of a model that nearly works.
        </p>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ metrics */

function Metrics({ m }: { m: Modelling }) {
  const best = m.best_model;
  const perm = m.permutation_test;
  const beatsNull = perm ? perm.empirical_p < 0.05 : null;

  const AVAILABLE = best
    ? [
        { label: "ROC AUC", value: best.roc_auc_mean.toFixed(3), sd: best.roc_auc_sd.toFixed(3), color: "var(--color-aqua)" },
        { label: "Balanced accuracy", value: best.balanced_accuracy_mean.toFixed(3), sd: best.balanced_accuracy_sd.toFixed(3), color: "var(--color-sky)" },
      ]
    : [];

  const NOT_COMPUTED = [
    ["Accuracy", "Not reported: with balanced classes and a near-chance model, raw accuracy would restate the balanced accuracy without adding information."],
    ["Precision, recall, F1", "Not computed. These need a chosen decision threshold, and no threshold is defensible for a model that does not beat its null."],
    ["PR-AUC", "Not computed by the evaluation script."],
    ["Confusion matrix, ROC and PR curves", "Not exported: the pipeline stores per-fold summary scores, not the out-of-fold predictions these plots need."],
    ["Calibration plot", "Not applicable. Calibration describes how well predicted probabilities match observed rates, which is only meaningful once a model discriminates."],
  ];

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr_1.15fr]">
      <Panel>
        <PanelHeader eyebrow="Performance metrics" title={best ? `Best model: ${best.model}` : "Performance"} description="Values validated by the evaluation script." />
        <div className="flex flex-col gap-5 p-5">
          <div className="grid grid-cols-2 gap-4">
            {AVAILABLE.map((a) => (
              <div key={a.label}>
                <div className="eyebrow">{a.label}</div>
                <div className="tabular mt-1 text-3xl font-semibold tracking-tight" style={{ color: a.color }}>
                  {a.value}
                </div>
                <div className="text-xs text-muted">± {a.sd} across folds</div>
              </div>
            ))}
          </div>

          <div className="border-t border-line/60 pt-4">
            <div className="eyebrow mb-2">Not available</div>
            <dl className="flex flex-col gap-2.5">
              {NOT_COMPUTED.map(([t, why]) => (
                <div key={t} className="flex gap-2.5">
                  <XCircle className="mt-0.5 size-3.5 shrink-0 text-muted/60" />
                  <div>
                    <dt className="text-[13px] text-ink/85">{t}</dt>
                    <dd className="text-xs leading-relaxed text-muted">{why}</dd>
                  </div>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelHeader
          eyebrow="Significance test"
          title="Does the model beat a shuffled-label null?"
          description="The same cross-validation is rerun on randomly permuted labels. If the real score sits inside that null distribution, the model has learned nothing."
          action={<ShieldAlert className="size-4 text-muted" />}
        />
        {!perm ? (
          <div className="p-5">
            <EmptyState variant="unavailable" title="Permutation test not generated" />
          </div>
        ) : (
          <div className="flex flex-col gap-5 p-5">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Metric label="Observed AUC" value={perm.observed_roc_auc.toFixed(3)} />
              <Metric label="Null mean" value={perm.null_mean.toFixed(3)} accent="var(--color-muted)" />
              <Metric label="Null 95th pct" value={perm.null_95th_percentile.toFixed(3)} accent="var(--color-amber)" />
              <Metric label="Empirical p" value={perm.empirical_p.toFixed(3)} accent={beatsNull ? "var(--color-mint)" : "var(--color-rose)"} hint={`${perm.n_permutations} permutations`} />
            </div>

            {/* observed score against the null distribution, on a 0.3–0.9 axis */}
            <div>
              <div className="relative h-14 rounded-lg border border-line/70 bg-void/50 px-3">
                {(() => {
                  const lo = 0.3;
                  const hi = 0.9;
                  const at = (v: number) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100))}%`;
                  return (
                    <>
                      <div
                        className="absolute inset-y-3 rounded bg-muted/20"
                        style={{ left: at(perm.null_mean), width: `calc(${at(perm.null_95th_percentile)} - ${at(perm.null_mean)})` }}
                        title="null mean to 95th percentile"
                      />
                      <div className="absolute inset-y-2 w-px bg-muted" style={{ left: at(perm.null_mean) }} />
                      <div className="absolute inset-y-2 w-px bg-amber" style={{ left: at(perm.null_95th_percentile) }} />
                      <div className="absolute inset-y-1 w-[2px] rounded bg-teal shadow-[0_0_10px_var(--color-aqua)]" style={{ left: at(perm.observed_roc_auc) }} />
                    </>
                  );
                })()}
              </div>
              <div className="mt-1 flex justify-between font-mono text-[10px] text-muted">
                <span>0.30</span>
                <span>0.60</span>
                <span>0.90</span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-[2px] bg-teal" /> observed
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-px bg-muted" /> null mean
                </span>
                <span className="flex items-center gap-1.5">
                  <span className="h-2.5 w-px bg-amber" /> null 95th percentile
                </span>
              </div>
            </div>

            <Notice tone={beatsNull ? "info" : "warn"}>
              {beatsNull ? (
                <>The observed score falls outside the shuffled-label distribution (p = {perm.empirical_p}), so the signal is unlikely to be chance.</>
              ) : (
                <>
                  The observed AUC of {perm.observed_roc_auc.toFixed(3)} sits below the null 95th percentile of {perm.null_95th_percentile.toFixed(3)} (p ={" "}
                  {perm.empirical_p}). Shuffling the labels reaches this score roughly one time in three, so <b>H3 is not supported</b>: these sequence features
                  do not predict detection at 60 °C.
                </>
              )}
            </Notice>
          </div>
        )}
      </Panel>
    </div>
  );
}

/* ------------------------------------------------------------------ feature importance */

function Features({ m }: { m: Modelling }) {
  const rows = useMemo(() => [...(m.feature_importance ?? []).slice(0, 12)].reverse(), [m.feature_importance]);
  const motion = useChartMotion(rows, 700);
  if (!rows.length) return null;
  return (
    <Panel>
      <PanelHeader
        eyebrow="Feature importance"
        title="Which features the models leaned on"
        description="Random-forest impurity importance and standardised logistic-regression coefficients, fitted on all labelled proteins."
        action={<Ruler className="size-4 text-muted" />}
      />
      <div className="p-5">
        <Notice tone="warn" className="mb-4">
          Importances describe a model that does not beat chance, so they explain the fit, not biology. They are shown for completeness and should not be read
          as “instability index drives PET activity”.
        </Notice>
        <ChartInView className="chart-hl h-[340px]">
          <ResponsiveContainer>
            <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 20, bottom: 22, left: 110 }}>
              <CartesianGrid {...gridProps} horizontal={false} />
              <XAxis type="number" {...axisProps} label={axisLabel("Random-forest impurity importance")} />
              <YAxis type="category" dataKey="feature" width={110} {...axisProps} />
              <Tooltip
                cursor={{ fill: "var(--chart-cursor)" }}
                content={({ payload }) => {
                  const r = payload?.[0]?.payload as (typeof rows)[number] | undefined;
                  return r ? (
                    <ChartTooltip
                      title={r.feature}
                      rows={[
                        { label: "Random forest importance", value: r.random_forest_importance.toFixed(4), color: "var(--color-aqua)" },
                        { label: "Logistic coefficient (std)", value: r.logistic_coefficient_std.toFixed(3), color: "var(--color-sky)" },
                      ]}
                    />
                  ) : null;
                }}
              />
              <Bar dataKey="random_forest_importance" fill="var(--color-aqua)" radius={[0, 3, 3, 0]} {...motion} />
            </BarChart>
          </ResponsiveContainer>
        </ChartInView>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ other evidence */

function OtherTests({ m }: { m: Modelling }) {
  const nulls = m.clustering_null ?? [];
  const tests = m.statistical_tests ?? [];
  return (
    <Panel>
      <PanelHeader
        eyebrow="Supporting analyses"
        title="Other results that were tested against a null"
        description="Clustering and group-difference results use the same discipline as the classifier: an observed value only counts if it beats a null model."
        action={<Layers className="size-4 text-muted" />}
      />
      <div className="p-5">
        <Tabs defaultValue="clustering">
          <TabsList>
            <TabsTrigger value="clustering">Clustering vs null</TabsTrigger>
            <TabsTrigger value="tests">Group differences</TabsTrigger>
          </TabsList>
          <div className="mt-4">
            <TabsContent value="clustering">
              {!nulls.length ? (
                <EmptyState variant="unavailable" title="Null baseline not generated" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-left text-xs">
                    <thead>
                      <tr className="text-muted">
                        {["Null model", "Metric", "Observed", "Null mean ± sd", "Null max", "Draws", "p"].map((h) => (
                          <th key={h} className="border-b border-line px-2 py-2 font-normal">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {nulls.map((r, i) => (
                        <tr key={i} className="border-b border-line/40 transition-colors duration-150 hover:bg-elevated/40">
                          <td className="px-2 py-2 font-mono text-muted">{r.null_model}</td>
                          <td className="px-2 py-2">{r.metric}</td>
                          <td className="tabular px-2 py-2 font-mono text-teal">{r.observed}</td>
                          <td className="tabular px-2 py-2 font-mono text-muted">
                            {r.null_mean} ± {r.null_sd}
                          </td>
                          <td className="tabular px-2 py-2 font-mono text-muted">{r.null_max}</td>
                          <td className="tabular px-2 py-2 font-mono text-muted">{r.n_draws}</td>
                          <td className="tabular px-2 py-2 font-mono">
                            <Badge color={r.empirical_p < 0.05 ? "var(--color-mint)" : "var(--color-amber)"} dot={false}>
                              {r.empirical_p}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-3 text-xs leading-relaxed text-muted">
                    The clustering is real: its silhouette clears every null by a wide margin. That is the part of the analysis the data does support, and it
                    is unsupervised, not predictive.
                  </p>
                </div>
              )}
            </TabsContent>
            <TabsContent value="tests">
              {!tests.length ? (
                <EmptyState variant="unavailable" title="Statistical tests not generated" />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-left text-xs">
                    <thead>
                      <tr className="text-muted">
                        {["Dataset", "Test", "Comparison", "p", "q (BH)", "Significant", "Detail"].map((h) => (
                          <th key={h} className="border-b border-line px-2 py-2 font-normal">
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {tests.map((t, i) => (
                        <tr key={i} className="border-b border-line/40 align-top transition-colors duration-150 hover:bg-elevated/40">
                          <td className="px-2 py-2 text-muted">{t.dataset}</td>
                          <td className="px-2 py-2">{t.test}</td>
                          <td className="px-2 py-2 font-mono text-[11px]">{t.comparison}</td>
                          <td className="tabular px-2 py-2 font-mono text-muted">{t.p_value}</td>
                          <td className="tabular px-2 py-2 font-mono">{t.q_value_bh}</td>
                          <td className="px-2 py-2">
                            {t["significant_q<0.05"] ? <CheckCircle2 className="size-4 text-mint" /> : <XCircle className="size-4 text-muted/60" />}
                          </td>
                          <td className="max-w-sm px-2 py-2 text-muted">{t.detail}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-3 max-w-3xl text-xs leading-relaxed text-muted">
                    The naive comparison across all PAZy assays finds strong group differences in assay temperature — but those are differences in what
                    researchers chose to test, not in enzyme behaviour. Inside the one standardised screen, where every protein met the same protocol, the same
                    comparison is not significant after correction. That is why H2 is reported as not confirmed.
                  </p>
                </div>
              )}
            </TabsContent>
          </div>
        </Tabs>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ independent validation */

function IndependentValidation() {
  return (
    <Panel>
      <PanelHeader eyebrow="Independent validation" title="Is there an external test set?" description="What an honest external evaluation would require, and why it has not been run." />
      <div className="grid gap-4 p-5 md:grid-cols-2">
        <div className="rounded-xl border border-line/70 bg-void/40 p-4">
          <div className="eyebrow mb-2 text-cyan">The one clean boundary</div>
          <p className="text-[13px] leading-relaxed text-muted">
            The PETML variant library and the 2025 screening library share no identical sequence, and only 2 of 214 screened enzymes exceed 95% identity to any
            PETML entry (median best identity 63%). That is a genuinely independent split at the sequence level.
          </p>
        </div>
        <div className="rounded-xl border border-amber/30 bg-amber/[0.05] p-4">
          <div className="eyebrow mb-2 text-amber">Why it is not used as a test set</div>
          <p className="text-[13px] leading-relaxed text-ink/85">
            Sequence independence is not assay compatibility. The PETML workbooks record an <span className="font-mono">Activity</span> column with no units,
            ranges that differ by orders of magnitude between studies, and several studies normalised to their own wild type. Those numbers cannot be put on one
            scale, so a model trained on the screen cannot be scored against them. PETML is therefore <b>not</b> presented as external validation here.
          </p>
        </div>
      </div>
      <div className="px-5 pb-5">
        <Notice tone="warn">
          A further trap: 128 of 214 assayed screen enzymes are at least 99% identical to a PAZy protein. Any evaluation that trains on PAZy and tests on the
          screen leaks most of its test set, and would report an accuracy that means nothing.
        </Notice>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ page */

export function ValidationView() {
  const res = useApi<Modelling>("/modelling");

  if (res.error)
    return (
      <Panel>
        <ErrorState message={res.error.message} onRetry={res.retry} />
      </Panel>
    );
  if (!res.data)
    return (
      <div className="flex flex-col gap-6">
        <Skeleton label="Loading model validation outputs" className="h-40 rounded-[14px]" />
        <Skeleton className="h-96 rounded-[14px]" />
      </div>
    );

  const m = res.data;

  if (!m.available)
    return (
      <Panel>
        <EmptyState variant="unavailable" title="Model outputs have not been generated">
          Run <span className="font-mono text-ink">python -m pet_explorer.pipeline --stage 5</span> to produce the model comparison, permutation test and
          feature importances. Until then this page has nothing validated to show.
        </EmptyState>
      </Panel>
    );

  return (
    <div className="flex flex-col gap-6">
      <Panel glow className="overflow-hidden">
        <div className="grid-bg absolute inset-0 opacity-25" />
        <div className="relative p-6 sm:p-8">
          <div className="eyebrow flex items-center gap-2 text-teal">
            <AlertTriangle className="size-4" /> Headline result
          </div>
          <h2 className="mt-3 max-w-3xl text-2xl font-semibold tracking-tight sm:text-3xl">
            The supervised model does not beat chance, and this page shows why
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-muted">
            A negative result reported properly is still a result. Everything below comes from the evaluation script: the target it was given, the splits that
            prevented leakage, the baselines it was measured against, and the permutation test it failed.
          </p>
        </div>
      </Panel>

      <Development m={m} />
      <Splitting m={m} />
      {m.comparison && <Comparison rows={m.comparison} />}
      <Metrics m={m} />
      <Features m={m} />
      <OtherTests m={m} />
      <IndependentValidation />

      <Panel>
        <PanelHeader eyebrow="Model limitations" title="What bounds this result" />
        <div className="stagger grid gap-3 p-5 md:grid-cols-2">
          {m.limitations.map((l) => (
            <div key={l.title} className="hover-card flex gap-3 rounded-lg border border-line/70 bg-void/40 p-4">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber" />
              <div>
                <div className="text-[13px] font-medium">{l.title}</div>
                <p className="mt-1 text-xs leading-relaxed text-muted">{l.detail}</p>
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 pb-5">
          <ul className="flex flex-col gap-1.5">
            {m.notes.map((n) => (
              <li key={n} className="text-xs leading-relaxed text-muted">
                · {n}
              </li>
            ))}
          </ul>
        </div>
      </Panel>
    </div>
  );
}
