import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import useApi from '../hooks/useApi'
import { listUsers, deleteUser } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import ErrorBanner from '../components/ErrorBanner'
import { TrashIcon, PlusIcon, SpinnerIcon } from '../components/icons'

const PAGE_SIZE = 20

export default function Users() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const { data, loading, error, reload } = useApi(() => listUsers({ page, size: PAGE_SIZE }), [page])
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  const items = data?.items || []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const handleDelete = async (e, user) => {
    e.stopPropagation()
    if (!window.confirm(`Delete ${user.full_name || user.username}? This account will be deactivated.`)) return

    setDeleteError(null)
    setDeletingId(user.id)
    try {
      await deleteUser(user.id)
      reload()
    } catch (err) {
      setDeleteError(extractErrorMessage(err, 'Could not delete this user.'))
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-end">
        <Link
          to="/users/new"
          className="flex items-center gap-1.5 rounded-lg bg-sky-500 px-3.5 py-2 text-sm font-semibold text-white transition-colors hover:bg-sky-600"
        >
          <PlusIcon className="h-4 w-4" />
          Add User
        </Link>
      </div>

      <ErrorBanner error={error} />
      <ErrorBanner error={deleteError} />

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Name</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Username</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Email</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Mobile</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Role</th>
                <th className="px-5 py-3 text-xs font-medium uppercase tracking-wide text-slate-500">Status</th>
                <th className="px-5 py-3 text-right text-xs font-medium uppercase tracking-wide text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-slate-500">
                    No users found.
                  </td>
                </tr>
              )}
              {items.map((u) => (
                <tr
                  key={u.id}
                  onClick={() => navigate(`/users/${u.id}`)}
                  className="cursor-pointer transition-colors hover:bg-slate-100"
                >
                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-medium text-slate-800">
                        {initials(u.full_name || u.username)}
                      </div>
                      <p className="truncate font-medium text-slate-800">{u.full_name || '—'}</p>
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-slate-600">@{u.username}</td>
                  <td className="px-5 py-3.5 text-slate-600">{u.email}</td>
                  <td className="px-5 py-3.5 text-slate-600">{u.mobile || '—'}</td>
                  <td className="px-5 py-3.5">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs capitalize text-slate-700 ring-1 ring-inset ring-slate-200">
                      {u.role.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-5 py-3.5">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs ring-1 ring-inset ${
                        u.is_active
                          ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                          : 'bg-red-50 text-red-700 ring-red-200'
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-red-400'}`} />
                      {u.is_active ? 'Active' : 'Deactivated'}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-right">
                    <button
                      type="button"
                      onClick={(e) => handleDelete(e, u)}
                      disabled={deletingId === u.id}
                      title="Delete user"
                      className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-red-50 hover:text-red-700 disabled:opacity-50"
                    >
                      {deletingId === u.id ? (
                        <SpinnerIcon className="h-4 w-4 animate-spin" />
                      ) : (
                        <TrashIcon className="h-4 w-4" />
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {total > 0 && (
          <div className="flex items-center justify-between border-t border-slate-200 px-5 py-3.5 text-xs text-slate-500">
            <span>
              {total} user{total === 1 ? '' : 's'} · page {page} of {totalPages}
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

function initials(name) {
  if (!name) return ''
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}
