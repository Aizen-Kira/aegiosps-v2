'use client'

import { useEffect, useState } from 'react'
import { Database } from 'lucide-react'

interface Trace {
  id: string
  incident: string
  duration: number
  status: string
  root_cause?: string
  eval_score?: number
}

export default function PhoenixTraceViewer({ refreshKey }: { refreshKey: number }) {
  const [traces, setTraces] = useState<Trace[]>([])

  useEffect(() => {
    const loadTraces = async () => {
      const response = await fetch('/api/traces')
      if (response.ok) {
        setTraces(await response.json())
      }
    }

    loadTraces().catch((error) => console.error('Error loading traces:', error))
  }, [refreshKey])

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950/70 p-5">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
        <Database size={22} className="text-violet-300" />
        Phoenix Trace Memory
      </h2>

      {traces.length === 0 ? (
        <div className="py-8 text-center text-sm text-slate-500">
          Stored traces will appear after the first resolution.
        </div>
      ) : (
        <div className="space-y-3">
          {traces.map((trace) => (
            <div key={trace.id} className="rounded-lg border border-slate-800 bg-slate-900/60 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-slate-200">{trace.id}</p>
                  {trace.root_cause && <p className="text-xs text-slate-500 mt-0.5">{trace.root_cause}</p>}
                </div>
                <div className="flex items-center gap-2">
                  {typeof trace.eval_score === 'number' && (
                    <div className="text-right">
                      <div className="text-xs text-slate-400">Eval</div>
                      <div className="text-sm font-semibold text-emerald-400">{Math.round(trace.eval_score * 100)}%</div>
                    </div>
                  )}

                  <span className="rounded bg-violet-500/10 px-2 py-1 text-xs text-violet-200">
                    {trace.duration.toFixed(1)}s
                  </span>
                </div>
              </div>
              <p className="mt-2 text-sm text-slate-400">{trace.incident}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
