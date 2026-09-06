import { Fragment, useState } from 'react'
import useApi from '../hooks/useApi'
import { listAuditLogs } from '../api/client'
import ErrorBanner from '../components/ErrorBanner'
import TextField from '../components/TextField'
import { HistoryIcon, ChevronDownIcon } from '../components/icons'

const PAGE_SIZE = 50

export default function AuditLogs() {
  const [page, setPage] = useState(1)
  const [action, setAction] = useState('')
  const [entityType, setEntityType] = useState('')
  const [expandedId, setExpandedId] = useState(null)

  const { data, loading, error } = useApi(
    () => listAuditLogs({ page, size: PAGE_SIZE, action: action || undefined, entity_type: entityType || undefined }),
    [page, action, entityType]
  )

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <TextField
          placeholder="Filter by action, e.g. LOGIN"
          value={action}
          onChange={(e) => { setAction(e.target.value.trim().toUpperCase()); setPage(1) }}
          className="max-w-[14rem]"
        />
        <TextField
          placeholder="Filter by entity, e.g. devices"
          value={entityType}
          onChange={(e) => { setEntityType(e.target.value.trim()); setPage(1) }}
          className="max-w-[14rem]"
        />
      </div>

      <ErrorBanner error={error} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">When</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">User</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Action</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Entity</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">IP</th>
                <th className="px-5 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-slate-500">
                    No audit log entries.
                  </td>
                </tr>
              )}
              {items.map((entry) => {
                const isExpanded = expandedId === entry.id
                const hasDetail = entry.old_value || entry.new_value
                return (
                  <Fragment key={entry.id}>
                    <tr
                      onClick={() => hasDetail && setExpandedId(isExpanded ? null : entry.id)}
                      className={`transition-colors hover:bg-slate-100 ${hasDetail ? 'cursor-pointer' : ''}`}
                    >
                      <td className="px-5 py-3 text-slate-600">
                        {entry.created_at ? new Date(entry.created_at).toLocaleString() : '—'}
                      </td>
                      <td className="px-5 py-3">
                        <span className="flex items-center gap-2 text-slate-800">
                          <HistoryIcon className="h-3.5 w-3.5 text-slate-500" />
                          {entry.username || 'System'}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className="rounded-full bg-slate-100 px-2.5 py-1 font-mono text-xs text-slate-700 ring-1 ring-inset ring-slate-200">
                          {entry.action}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-slate-600">
                        {entry.entity_type ? `${entry.entity_type}${entry.entity_id ? ` #${entry.entity_id}` : ''}` : '—'}
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-slate-500">{entry.ip_address || '—'}</td>
                      <td className="px-5 py-3 text-right">
                        {hasDetail && (
                          <ChevronDownIcon className={`ml-auto h-4 w-4 text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                        )}
                      </td>
                    </tr>
                    {isExpanded && hasDetail && (
                      <tr className="bg-slate-50">
                        <td colSpan={6} className="px-5 py-4">
                          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            {entry.old_value && (
                              <div>
                                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Before</p>
                                <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
                                  {JSON.stringify(entry.old_value, null, 2)}
                                </pre>
                              </div>
                            )}
                            {entry.new_value && (
                              <div>
                                <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">After</p>
                                <pre className="overflow-x-auto rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-700">
                                  {JSON.stringify(entry.new_value, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500">
            <span>
              {total} entr{total === 1 ? 'y' : 'ies'} · page {page} of {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="rounded-lg border border-slate-200 bg-slate-100 px-3 py-1.5 text-slate-700 hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
