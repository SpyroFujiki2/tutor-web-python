import { useEffect, useState } from 'react'
import { loadCollection } from './collection-utils.js'

export function useCollection(api, path) {
  const [state, setState] = useState({})
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    loadCollection(api, path, controller.signal).then(
      (data) => { if (!controller.signal.aborted) setState({ path, revision, data }) },
      (error) => { if (!controller.signal.aborted) setState({ path, revision, error: error.message }) },
    )
    return () => controller.abort()
  }, [api, path, revision])
  const current = state.path === path && state.revision === revision
  return { data: current ? state.data : null, error: current ? state.error : null,
    loading: !current || (!state.data && !state.error), reload: () => setRevision((value) => value + 1) }
}

