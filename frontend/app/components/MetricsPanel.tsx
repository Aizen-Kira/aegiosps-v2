'use client'

import { TrendingDown, Clock, Zap, Database } from 'lucide-react'

interface MetricsPanelProps {
  metrics: {
    total_incidents: number
    avg_resolution_time: number
    improvement_ratio: number
    traces_stored: number
  }
}

export default function MetricsPanel({ metrics }: MetricsPanelProps) {
  const metricCards = [
    {
      label: 'Total Incidents',
      value: metrics.total_incidents,
      icon: Zap,
      color: 'text-blue-500',
      bgColor: 'bg-blue-900/20',
    },
    {
      label: 'Avg Resolution Time',
      value: `${metrics.avg_resolution_time.toFixed(1)}s`,
      icon: Clock,
      color: 'text-yellow-500',
      bgColor: 'bg-yellow-900/20',
    },
    {
      label: 'Improvement Ratio',
      value: `${metrics.improvement_ratio.toFixed(1)}%`,
      icon: TrendingDown,
      color: 'text-green-500',
      bgColor: 'bg-green-900/20',
    },
    {
      label: 'Traces Stored',
      value: metrics.traces_stored,
      icon: Database,
      color: 'text-purple-500',
      bgColor: 'bg-purple-900/20',
    },
  ]

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {metricCards.map((card, idx) => {
        const Icon = card.icon
        return (
          <div
            key={idx}
            className={`${card.bgColor} rounded-lg p-4 border border-gray-800 hover:border-gray-700 transition-colors`}
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">
                {card.label}
              </p>
              <Icon size={18} className={card.color} />
            </div>
            <p className={`text-2xl font-bold ${card.color}`}>
              {card.value}
            </p>
          </div>
        )
      })}
    </div>
  )
}
