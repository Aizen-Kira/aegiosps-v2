'use client'

import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from 'recharts'
import { TrendingDown } from 'lucide-react'

interface LearningChartProps {
  data: Array<{ incident: number; duration: number; isMemoryHit?: boolean; synthetic?: boolean }>
}

export default function LearningChart({ data }: LearningChartProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-6 border border-gray-800">
      <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
        <TrendingDown size={24} className="text-green-500" />
        Learning Curve
      </h2>

      {data.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          Resolve incidents to see the learning curve
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#444" />
            <XAxis
              dataKey="incident"
              label={{ value: 'Incident #', position: 'insideBottomRight', offset: -5 }}
              stroke="#888"
            />
            <YAxis
              label={{ value: 'Resolution Time (seconds)', angle: -90, position: 'insideLeft' }}
              stroke="#888"
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #444' }}
              labelStyle={{ color: '#e0e0e0' }}
              formatter={(value: any) => `${value.toFixed(1)}s`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="duration"
              stroke="#10b981"
              dot={(props: any) => {
                const { cx, cy, payload, key } = props
                return (
                  <circle
                    key={key}
                    cx={cx}
                    cy={cy}
                    r={payload.synthetic ? 3 : 5}
                    fill={payload.isMemoryHit ? '#8b5cf6' : '#10b981'}
                    opacity={payload.synthetic ? 0.5 : 1}
                    stroke="none"
                  />
                )
              }}
              activeDot={{ r: 7 }}
              name="Resolution Time"
              strokeWidth={2}
            />
            <ReferenceLine
              y={8}
              stroke="#8b5cf6"
              strokeDasharray="4 4"
              label={{ value: 'Memory baseline', position: 'insideTopRight', fill: '#8b5cf6', fontSize: 11 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
