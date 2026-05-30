'use client'

import { useEffect, useState } from 'react'
import { Brain, CheckCircle2, Clock, Database, GitBranch, RefreshCcw, Search, ShieldCheck, Sparkles } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

interface TimelineEvent {
  step: string
  tool: string
  message: string
  timestamp: number
  confidence?: number
  data?: Record<string, any>
}

interface ReasoningTimelineProps {
  events: TimelineEvent[]
  isLoading: boolean
}

const stepColors: Record<string, string> = {
  MEMORY: 'memory',
  DETECT: 'detect',
  INVESTIGATE: 'investigate',
  REASON: 'reason',
  REMEDIATE: 'remediate',
  VERIFY: 'verify',
  LEARN: 'learn',
  COMPLETE: 'complete',
}

const stepLabels: Record<string, string> = {
  MEMORY: 'Memory',
  DETECT: 'Detect',
  INVESTIGATE: 'Investigate',
  REASON: 'Reason',
  REMEDIATE: 'Remediate',
  VERIFY: 'Verify',
  LEARN: 'Learn',
  COMPLETE: 'Complete',
}

const stepIcons: Record<string, LucideIcon> = {
  MEMORY: Brain,
  DETECT: Search,
  INVESTIGATE: GitBranch,
  REASON: Sparkles,
  REMEDIATE: RefreshCcw,
  VERIFY: ShieldCheck,
  LEARN: Database,
  COMPLETE: CheckCircle2,
}

export default function ReasoningTimeline({ events, isLoading }: ReasoningTimelineProps) {
  const [displayedEvents, setDisplayedEvents] = useState<TimelineEvent[]>([])

  useEffect(() => {
    if (events.length === 0) {
      setDisplayedEvents((prev) => (prev.length === 0 ? prev : []))
      return
    }

    setDisplayedEvents((prev) => {
      if (events.length <= prev.length) return prev
      return [...prev, events[prev.length]]
    })
  }, [events])

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950/70 p-5">
      <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold text-white">
        <Clock size={22} className="text-cyan-300" />
        Reasoning Timeline
      </h2>

      <div className="max-h-96 space-y-2 overflow-y-auto">
        {displayedEvents.length === 0 && !isLoading && (
          <div className="py-8 text-center text-sm text-slate-500">
            Submit an incident to see the reasoning timeline
          </div>
        )}

        {displayedEvents.map((event, idx) => {
          const Icon = stepIcons[event.step] || Clock

          return (
            <div
              key={`${event.step}-${idx}`}
              className={`timeline-item ${stepColors[event.step]?.toLowerCase() || 'default'} animate-in fade-in slide-in-from-left-4 duration-300`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <Icon size={15} className="text-slate-300" />
                    <span className="text-sm font-semibold text-slate-200">
                      {stepLabels[event.step] || event.step}
                    </span>
                    <span className="rounded bg-slate-800 px-2 py-1 text-xs text-slate-400">
                      {event.tool}
                    </span>
                  </div>
                  <p className="text-sm leading-6 text-slate-400">{event.message}</p>
                  {event.step === 'MEMORY' && event.data?.candidates && event.data.candidates.length > 0 && (
                    <div className="mt-3 rounded border border-slate-800 bg-slate-900/40 p-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-xs text-slate-400">Top match</div>
                          <div className="text-sm font-medium text-slate-200">{event.data.candidates[0].description}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-slate-400">Similarity</div>
                          <div className="text-sm font-semibold text-slate-200">{Math.round(event.data.candidates[0].similarity * 100)}%</div>
                        </div>
                      </div>

                      <div className="mt-3 flex items-center gap-2">
                        <div className="h-2 flex-1 overflow-hidden rounded bg-slate-800">
                          <div
                            className="h-full rounded bg-emerald-400 transition-all duration-700 ease-out"
                            style={{ width: `${Math.round(event.data.candidates[0].combined_score * 100)}%` }}
                          />
                        </div>
                        <div className="text-[11px] text-slate-400">
                          {Math.round(event.data.candidates[0].combined_score * 100)}% rank
                        </div>
                      </div>
                    </div>
                  )}
                  {(event.step === 'REASON' || event.step === 'REMEDIATE' || event.step === 'VERIFY') && typeof event.confidence === 'number' && (
                    <div className="mt-3">
                      <div className="flex items-center justify-between mb-2">
                        <div className="text-xs text-slate-400">Confidence</div>
                        <div className="text-[11px] text-slate-500">{Math.round(event.confidence * 100)}%</div>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded bg-slate-800">
                        <div
                          className={`h-full rounded transition-all duration-900 ease-out ${event.confidence > 0.8 ? 'bg-emerald-400' : event.confidence > 0.5 ? 'bg-yellow-400' : 'bg-rose-400'}`}
                          style={{ width: `${event.confidence * 100}%`, boxShadow: `0 0 12px rgba(16, 185, 129, ${event.confidence})` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
                <div className="ml-4 shrink-0 text-xs text-slate-600">
                  {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </div>
              </div>
            </div>
          )
        })}

        {isLoading && displayedEvents.length > 0 && (
          <div className="timeline-item animate-pulse">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 animate-spin rounded-full border border-slate-500 border-t-cyan-300" />
              <span className="text-sm text-slate-500">Processing...</span>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
