"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Loader2, RefreshCw, ShieldCheck, Sparkles } from "lucide-react";
import AIAlphaRadarTab from "./AIAlphaRadarTab";

// Craft: thin-stroke icons only. 1.5 matches the hairline borders; the Lucide
// default of 2 reads as a second, heavier line weight on the same surface.
const ICON = { size: 15, strokeWidth: 1.5 } as const;

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ACTION_COLOR,
  getRecommendations,
  getRecommendationsForPortfolio,
  type RecommendationRow,
  type RecommendationsResponse,
} from "@/lib/recommendationsApi";
import { formatCurrency, formatNumber, loadPortfolio } from "@/lib/portfolioApi";

const INDICES = ["NIFTY50", "NIFTY100", "NIFTY200", "NIFTY500"];

// A cold scan with fundamentals is tens of seconds of scraping, so the page
// opens on the cheap scan and lets the user pay for depth deliberately.
const DEPTHS = [
  { key: "fast", label: "Fast scan", note: "200 names, prices only", query: { universe_limit: 200, with_fundamentals: false } },
  { key: "full", label: "Full scan", note: "300 names, with fundamentals", query: { universe_limit: 300, with_fundamentals: true, fundamental_limit: 80 } },
];

export default function RecommendationsConsole() {
  const [index, setIndex] = useState("NIFTY500");
  const [depth, setDepth] = useState("fast");
  const [usePortfolio, setUsePortfolio] = useState(false);
  const [holdingsCount, setHoldingsCount] = useState(0);
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = loadPortfolio();
    setHoldingsCount(stored.equity.length);
    setUsePortfolio(stored.equity.length > 0);
  }, []);

  const run = useCallback(
    async (withPortfolio: boolean) => {
      setLoading(true);
      setError(null);
      const query = {
        index,
        ...(DEPTHS.find((d) => d.key === depth)?.query ?? {}),
      };
      try {
        const stored = loadPortfolio();
        const result =
          withPortfolio && stored.equity.length > 0
            ? await getRecommendationsForPortfolio(stored, query)
            : await getRecommendations(query);
        setData(result);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : String(caught));
      } finally {
        setLoading(false);
      }
    },
    [index, depth]
  );

  useEffect(() => {
    void run(usePortfolio);
    // Re-runs when the universe or depth changes; the backend caches a scan
    // for an hour, so flipping back to a previous setting is instant.
  }, [index, depth, usePortfolio, run]);

  const buys = data?.buy ?? [];
  const sells = data?.sell ?? [];
  const keeps = data?.holdings_to_keep ?? [];

  return (
    <div className="app-container animate-fade-in flex flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-heading text-[28px] font-semibold tracking-tight">
            Buy &amp; Sell Recommendations
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Every name graded on one model — technicals and fundamentals blended into a single
            0–100 score, with the evidence attached. Buys come from the universe you do not own;
            sells are judged against what you hold, priced after capital-gains tax.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select value={index} onValueChange={(value) => value && setIndex(value)}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="Universe" />
            </SelectTrigger>
            <SelectContent>
              {INDICES.map((name) => (
                <SelectItem key={name} value={name}>
                  {name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={depth} onValueChange={(value) => value && setDepth(value)}>
            <SelectTrigger className="w-[220px]">
              <SelectValue placeholder="Scan depth" />
            </SelectTrigger>
            <SelectContent>
              {DEPTHS.map((option) => (
                <SelectItem key={option.key} value={option.key}>
                  {option.label} — {option.note}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" onClick={() => void run(usePortfolio)} disabled={loading}>
            {loading ? (
              <Loader2 className="animate-spin" {...ICON} />
            ) : (
              <RefreshCw {...ICON} />
            )}
            {loading ? "Scanning…" : "Rescan"}
          </Button>
        </div>
      </header>

      {holdingsCount > 0 && (
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
          <ShieldCheck {...ICON} className="text-muted-foreground" />
          <span className="text-sm text-muted-foreground">
            {holdingsCount} holding{holdingsCount === 1 ? "" : "s"} found in this browser.
          </span>
          <Button
            size="sm"
            variant={usePortfolio ? "default" : "outline"}
            onClick={() => setUsePortfolio(!usePortfolio)}
            disabled={loading}
          >
            {usePortfolio ? "Judging sells against your portfolio" : "Use my portfolio"}
          </Button>
        </div>
      )}

      {holdingsCount === 0 && (
        <Alert>
          <AlertTitle>No holdings in this browser</AlertTitle>
          <AlertDescription>
            The sell list is universe-wide until you add holdings — names to avoid, or to exit if
            you own them. <Link href="/portfolio" className="underline">Add your portfolio</Link>{" "}
            for position-level exit calls with the tax on each.
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTitle>Could not build recommendations</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Buy candidates"
          value={loading && !data ? null : String(buys.length)}
          hint="Scoring 65 or better, not already held"
          tone="var(--color-buy)"
          icon={<ArrowUpRight {...ICON} />}
        />
        <StatCard
          label={data?.basis === "portfolio" ? "Sell candidates" : "Avoid list"}
          value={loading && !data ? null : String(sells.length)}
          hint={data?.basis === "portfolio" ? "Holdings below 45" : "Universe names below 45"}
          tone="var(--color-sell)"
          icon={<ArrowDownRight {...ICON} />}
        />
        <StatCard
          label="Universe priced"
          value={loading && !data ? null : `${data?.universe.scanned ?? 0} / ${data?.universe.size ?? 0}`}
          hint={`${data?.universe.fundamentals_scored ?? 0} also scored on fundamentals`}
        />
        <StatCard
          label="Scan"
          value={loading && !data ? null : data?.universe.cached ? "Cached" : "Fresh"}
          hint={data ? new Date(data.as_of).toLocaleString("en-IN") : "—"}
        />
      </div>

      <Tabs defaultValue="buy">
        <TabsList>
          <TabsTrigger value="buy">Buy ({buys.length})</TabsTrigger>
          <TabsTrigger value="sell">
            {data?.basis === "portfolio" ? "Sell" : "Avoid"} ({sells.length})
          </TabsTrigger>
          <TabsTrigger value="keep">Hold ({keeps.length})</TabsTrigger>
          <TabsTrigger value="ai-radar" className="flex items-center gap-1.5 text-blue-400 font-semibold">
            <Sparkles size={13} className="text-blue-400" />
            AI Alpha Radar (Deciles)
          </TabsTrigger>
        </TabsList>

        <TabsContent value="buy">
          <RecommendationTable
            rows={buys}
            loading={loading && !data}
            emptyMessage="Nothing in this universe currently scores a Buy. That is an answer, not an error — widen the universe or run the full scan."
          />
        </TabsContent>

        <TabsContent value="sell">
          <RecommendationTable
            rows={sells}
            loading={loading && !data}
            showPosition={data?.basis === "portfolio"}
            emptyMessage={
              data?.basis === "portfolio"
                ? "Nothing you hold is scoring below 45. No exits suggested."
                : "Nothing in this universe scores low enough to flag."
            }
          />
        </TabsContent>

        <TabsContent value="keep">
          <RecommendationTable
            rows={keeps}
            loading={loading && !data}
            showPosition
            emptyMessage="Holdings that score Hold or better will appear here."
          />
        </TabsContent>

        <TabsContent value="ai-radar">
          <AIAlphaRadarTab />
        </TabsContent>
      </Tabs>

      {data && data.notes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Notes from this run</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
              {data.notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">
        {data?.disclaimer ??
          "Diagnostic scores over public data, not investment advice. No order is ever placed."}
      </p>
    </div>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
  icon,
}: {
  label: string;
  value: string | null;
  hint: string;
  tone?: string;
  icon?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="craft-meta">{label}</CardDescription>
        <CardTitle className="text-2xl font-semibold tracking-tight tabular-nums" style={tone ? { color: tone } : undefined}>
          {value === null ? <Skeleton className="h-7 w-20" /> : value}
        </CardTitle>
        {icon && <CardAction style={tone ? { color: tone } : undefined}>{icon}</CardAction>}
      </CardHeader>
      <CardContent>
        <p className="text-xs leading-snug text-muted-foreground">{hint}</p>
      </CardContent>
    </Card>
  );
}

function RecommendationTable({
  rows,
  loading,
  showPosition = false,
  emptyMessage,
}: {
  rows: RecommendationRow[];
  loading: boolean;
  showPosition?: boolean;
  emptyMessage: string;
}) {
  if (loading) {
    return (
      <div className="space-y-2 py-4">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-11 w-full" />
        ))}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <Card className="mt-4">
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          {emptyMessage}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="mt-4 overflow-x-auto rounded-lg border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="craft-meta w-[240px]">Stock</TableHead>
            <TableHead className="craft-meta text-right">Price</TableHead>
            <TableHead className="craft-meta text-right">Score</TableHead>
            <TableHead className="craft-meta">Call</TableHead>
            <TableHead className="craft-meta">Conviction</TableHead>
            {showPosition && <TableHead className="craft-meta text-right">Your position</TableHead>}
            {showPosition && <TableHead className="craft-meta text-right">Exit tax</TableHead>}
            <TableHead className="craft-meta">Why</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.symbol}>
              <TableCell>
                <Link href={`/analyse/${row.symbol}`} className="font-medium hover:underline">
                  {row.symbol}
                </Link>
                <div className="text-xs text-muted-foreground">
                  {row.name}
                  {row.sector ? ` · ${row.sector}` : ""}
                  {row.off_index ? " · outside scanned index" : ""}
                </div>
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {row.price === null ? "—" : formatNumber(row.price)}
              </TableCell>
              <TableCell className="text-right tabular-nums font-medium">
                {row.score === null ? "—" : row.score.toFixed(1)}
                <div className="craft-meta mt-0.5">{Math.round(row.coverage * 100)}% evidence</div>
              </TableCell>
              <TableCell>
                <span
                  className="craft-pill"
                  style={{ color: ACTION_COLOR[row.action ?? ""] ?? "var(--text-muted)" }}
                >
                  {row.action_label ?? "Unscored"}
                </span>
              </TableCell>
              <TableCell className="craft-meta text-muted-foreground">
                {row.conviction ?? "—"}
              </TableCell>
              {showPosition && (
                <TableCell className="text-right tabular-nums">
                  {row.position ? (
                    <>
                      <div>{formatCurrency(row.position.current_value_inr ?? null)}</div>
                      <div
                        className="text-xs"
                        style={{
                          color:
                            (row.position.unrealised_pnl_inr ?? 0) >= 0
                              ? "var(--color-buy)"
                              : "var(--color-sell)",
                        }}
                      >
                        {formatCurrency(row.position.unrealised_pnl_inr ?? null)}
                      </div>
                    </>
                  ) : (
                    "—"
                  )}
                </TableCell>
              )}
              {showPosition && (
                <TableCell className="text-right tabular-nums">
                  {row.position ? (
                    <>
                      <div>{formatCurrency(row.position.estimated_exit_tax_inr ?? null)}</div>
                      <div className="craft-meta mt-0.5">
                        {row.position.term === "long" ? "LTCG 12.5%" : "STCG 20%"}
                        {row.position.days_to_long_term
                          ? ` · ${row.position.days_to_long_term}d to LTCG`
                          : ""}
                      </div>
                    </>
                  ) : (
                    "—"
                  )}
                </TableCell>
              )}
              <TableCell className="max-w-[420px]">
                <ul className="space-y-0.5 text-xs text-muted-foreground">
                  {row.reasons.slice(0, 3).map((reason, i) => (
                    <li key={i}>{reason}</li>
                  ))}
                  {row.reasons.length === 0 && <li>No evidence recorded.</li>}
                </ul>
                {row.position?.note && (
                  <>
                    <Separator className="my-2" />
                    <p className="text-xs text-muted-foreground">{row.position.note}</p>
                  </>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
