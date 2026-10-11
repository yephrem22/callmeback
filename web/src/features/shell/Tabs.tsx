// Bottom tab panels (PLAN.md §14.9): Payments (10A + 11A), Vendors (14A), Audit log (9B), DevRev cases, Demo controls.
import { X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Switch } from "@/components/ui/switch";
import { ChangeCases } from "@/features/devrev/ChangeCases";
import { AuditTimeline } from "@/features/evidence/AuditList";
import { KpiTiles } from "@/features/payments/KpiStrip";
import { LedgerTable } from "@/features/payments/LedgerTable";
import { BankHistoryCards } from "@/features/vendors/BankHistory";
import { postAiMode, postReset, postSimulate, useAction, useAudit, useHealth, usePayments, useStats, useVendors } from "@/lib/api";
import type { InvoiceDetail } from "@/lib/types";
import type { Tab } from "@/lib/route";
import { useState } from "react";

function PaymentsTab() {
  const { data: stats } = useStats();
  const { data: payments } = usePayments();
  return (
    <div className="space-y-4">
      {stats && <KpiTiles stats={stats} />}
      {payments && <LedgerTable view={payments} />}
    </div>
  );
}

function VendorsTab() {
  const { data: vendors = [] } = useVendors();
  return (
    <div className="grid grid-cols-3 gap-4">
      {vendors.map((v) => (
        <section key={v.id} className="rounded-md border border-border p-3">
          <h4 className="font-medium">{v.name}</h4>
          <p className="text-sm text-muted-foreground">{v.domains.join(", ")} · phone on file <span className="mono">{v.phone_masked}</span></p>
          <p className="mt-1 text-sm">{v.bank_masked}</p>
          <div className="mt-3"><BankHistoryCards vendor={v} /></div>
        </section>
      ))}
    </div>
  );
}

function AuditTab() {
  const { data } = useAudit();
  if (!data) return null;
  return <AuditTimeline rows={data.entries} chainOk={data.chain_ok} brokenAt={data.broken_at} exportName="all" />;
}

function DemoTab({ onReset, selected }: { onReset?: () => void; selected?: InvoiceDetail | null }) {
  const { data: health } = useHealth();
  const reset = useAction(postReset);
  const aiMode = useAction(postAiMode);
  const simulate = useAction(postSimulate);
  const [confirm, setConfirm] = useState(false);
  const [last4, setLast4] = useState("4455");
  const canSimulate = !!selected?.actions.can_simulate;
  return (
    <div className="flex flex-wrap items-center gap-6 text-sm">
      <Button variant="outline" onClick={() => setConfirm(true)}>Reset demo</Button>
      <div className="flex items-center gap-2">
        <Switch id="ai" checked={health?.ai_mode === "live"} onCheckedChange={(on) => aiMode.mutate([on ? "live" : "off"], { onSuccess: () => toast(on ? "AI live" : "AI off (rules only)") })} />
        <Label htmlFor="ai">AI live</Label>
      </div>
      {/* PLAN.md §19.2 backup plan: the phone didn't ring → answer for the vendor from here. */}
      <div className="flex flex-wrap items-center gap-2" aria-label="Simulate the vendor's answer">
        <Label htmlFor="last4">Last four for a yes</Label>
        <Input id="last4" className="mono w-20" inputMode="numeric" maxLength={4} value={last4}
               onChange={(e) => setLast4(e.target.value.replace(/\D/g, "").slice(0, 4))} />
        {canSimulate && selected ? (
          <>
            <Button variant="outline" disabled={simulate.isPending}
                    onClick={() => simulate.mutate([selected.id, "yes", last4 || null], { onSuccess: () => toast("Simulated: vendor said yes") })}>
              Vendor says yes
            </Button>
            <Button variant="outline" disabled={simulate.isPending}
                    onClick={() => simulate.mutate([selected.id, "no", null], { onSuccess: () => toast("Simulated: vendor said no") })}>
              Vendor says no
            </Button>
            <span className="text-muted-foreground">for {selected.vendor?.name ?? selected.email.from_name} {selected.invoice_number ?? ""}</span>
          </>
        ) : (
          <span className="text-muted-foreground">Select a case that is calling, or a retryable hold, to simulate the vendor's answer.</span>
        )}
      </div>
      <Dialog open={confirm} onOpenChange={setConfirm}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset the demo?</DialogTitle>
            <DialogDescription>Wipes invoices, calls, payments and the audit chain, and reseeds the vendors. DevRev cases are kept.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirm(false)}>Keep everything</Button>
            <Button onClick={() => {
              onReset?.();      // clear the selection first, so the refresh never re-fetches a deleted invoice
              reset.mutate([], { onSuccess: () => toast.success("Demo reset") });
              setConfirm(false);
            }}>Reset demo</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const TITLES: Record<Exclude<Tab, null>, string> = { payments: "Payments", vendors: "Vendors", audit: "Audit log", devrev: "DevRev cases", demo: "Demo controls" };

export function BottomTabs({ tab, onClose, onReset, selected }: {
  tab: Exclude<Tab, null>; onClose: () => void; onReset?: () => void; selected?: InvoiceDetail | null;
}) {
  return (
    <section className="border-t border-border bg-card" aria-label={TITLES[tab]}>
      <div className="flex items-center justify-between px-4 pt-2">
        <h3 className="font-medium">{TITLES[tab]}</h3>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel"><X className="size-4" /></Button>
      </div>
      <ScrollArea className="h-64 px-4 pb-3">
        {tab === "payments" && <PaymentsTab />}
        {tab === "vendors" && <VendorsTab />}
        {tab === "audit" && <AuditTab />}
        {tab === "devrev" && <ChangeCases />}
        {tab === "demo" && <DemoTab onReset={onReset} selected={selected} />}
      </ScrollArea>
    </section>
  );
}
