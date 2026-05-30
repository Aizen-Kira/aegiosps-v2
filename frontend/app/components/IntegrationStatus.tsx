'use client'

import { Activity, Bot, Database, GitBranch, RefreshCcw } from 'lucide-react'

interface IntegrationStatusProps {
  activeTools: Set<string>
}

const integrations = [
  { name: 'Arize Phoenix', key: 'phoenix', icon: Database },
  { name: 'Fivetran', key: 'fivetran', icon: RefreshCcw },
  { name: 'GitLab', key: 'gitlab', icon: GitBranch },
  { name: 'Gemini', key: 'gemini', icon: Bot },
]

export default function IntegrationStatus({ activeTools }: IntegrationStatusProps) {
  return (
    <section className="rounded-lg border border-slate-800 bg-slate-950/70 p-5">
      <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-white">
        <Activity size={22} className="text-emerald-300" />
        Integration Status
      </h2>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-1">
        {integrations.map((integration) => {
          const Icon = integration.icon
          const active = activeTools.has(integration.key)

          return (
            <div
              key={integration.key}
              className={`rounded-lg border p-3 transition-all ${
                active
                  ? 'border-emerald-500/70 bg-emerald-500/10'
                  : 'border-slate-800 bg-slate-900/60'
              }`}
            >
              <div className="flex items-center gap-2">
                <Icon size={18} className={active ? 'text-emerald-300' : 'text-slate-500'} />
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-300">{integration.name}</p>
                  <p className="text-xs text-slate-500">{active ? 'Queried' : 'Ready'}</p>
                </div>
                <div className={`h-2 w-2 rounded-full ${active ? 'animate-pulse bg-emerald-300' : 'bg-slate-700'}`} />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
