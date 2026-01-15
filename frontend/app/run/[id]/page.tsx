'use client';

import { useEffect, useState, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { fetchRunById, Run, Step, CandidateDecision } from '@/lib/api';

export default function RunDetail() {
  const params = useParams();
  const router = useRouter();
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedStep, setSelectedStep] = useState<Step | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadRun = useCallback(async (id: string) => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchRunById(id);
      setRun(data);
      if (data.steps && data.steps.length > 0 && !selectedStep) {
        setSelectedStep(data.steps[0]);
      } else if (data.steps && selectedStep) {
        const updatedStep = data.steps.find(s => s.id === selectedStep.id);
        if (updatedStep) setSelectedStep(updatedStep);
      }
      setLastUpdated(new Date());
    } catch (err) {
      setError('Failed to load run details.');
    } finally {
      setLoading(false);
    }
  }, [selectedStep]);

  useEffect(() => {
    if (params.id) {
      loadRun(params.id as string);
    }
  }, [params.id]);

  useEffect(() => {
    if (autoRefresh && params.id) {
      const interval = setInterval(() => loadRun(params.id as string), 3000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, params.id, loadRun]);

  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"></div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="bg-red-50 border border-red-200 rounded-md p-4">
            <p className="text-red-800">{error || 'Run not found'}</p>
          </div>
          <Link href="/" className="mt-4 inline-block text-blue-600 hover:text-blue-900">
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6">
          <div className="flex justify-between items-start mb-4">
            <Link href="/" className="text-blue-600 hover:text-blue-900 text-sm">
              ← Back to Dashboard
            </Link>
            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2 text-sm text-gray-600">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                Auto-refresh
              </label>
              <button
                onClick={() => loadRun(params.id as string)}
                disabled={loading}
                className="px-4 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Refresh'}
              </button>
            </div>
          </div>
          <h1 className="text-3xl font-light text-gray-900 mb-2">{run.pipeline_type}</h1>
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <span
              className={`px-3 py-1 rounded-full text-xs font-semibold ${
                run.status === 'SUCCESS'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {run.status}
            </span>
            <span>Duration: {formatDuration(run.duration_ms)}</span>
            <span>{formatDate(run.started_at)}</span>
            {lastUpdated && (
              <span className="text-xs text-gray-400">
                Updated: {lastUpdated.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Metadata */}
        {run.metadata && Object.keys(run.metadata).length > 0 && (
          <div className="mb-6 bg-white rounded-lg shadow-sm p-4">
            <h2 className="text-lg font-medium text-gray-900 mb-3">Metadata</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(run.metadata).map(([key, value]) => (
                <div key={key}>
                  <p className="text-xs text-gray-500">{key}</p>
                  <p className="text-sm text-gray-900 font-medium">{String(value)}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Steps */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Steps List */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow-sm overflow-hidden">
              <div className="p-4 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">Steps</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {run.steps && run.steps.length > 0 ? (
                  run.steps.map((step, index) => (
                    <button
                      key={step.id}
                      onClick={() => setSelectedStep(step)}
                      className={`w-full text-left p-4 hover:bg-gray-50 transition-colors ${
                        selectedStep?.id === step.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-gray-900">
                          {index + 1}. {step.step_name}
                        </span>
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-semibold ${
                            step.status === 'SUCCESS'
                              ? 'bg-green-100 text-green-800'
                              : 'bg-red-100 text-red-800'
                          }`}
                        >
                          {step.status}
                        </span>
                      </div>
                      <div className="text-xs text-gray-500">
                        <span className="inline-block px-2 py-0.5 bg-gray-100 rounded mr-2">
                          {step.step_type}
                        </span>
                        <span>{formatDuration(step.duration_ms)}</span>
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="p-4 text-center text-gray-600">No steps recorded</div>
                )}
              </div>
            </div>
          </div>

          {/* Step Details */}
          <div className="lg:col-span-2">
            {selectedStep ? (
              <div className="bg-white rounded-lg shadow-sm">
                <div className="p-4 border-b border-gray-200">
                  <h2 className="text-lg font-medium text-gray-900">{selectedStep.step_name}</h2>
                  <p className="text-sm text-gray-600 mt-1">Type: {selectedStep.step_type}</p>
                </div>

                {/* Stats */}
                {selectedStep.stats && Object.keys(selectedStep.stats).length > 0 && (
                  <div className="p-4 border-b border-gray-200">
                    <h3 className="text-sm font-medium text-gray-900 mb-3">Statistics</h3>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                      {Object.entries(selectedStep.stats).map(([key, value]) => (
                        <div key={key} className="bg-gray-50 p-3 rounded">
                          <p className="text-xs text-gray-600">{key}</p>
                          <p className="text-lg font-medium text-gray-900">
                            {typeof value === 'number' ? value.toFixed(2) : String(value)}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Candidates */}
                <div className="p-4">
                  <h3 className="text-sm font-medium text-gray-900 mb-3">
                    Candidates ({selectedStep.candidates?.length || 0})
                  </h3>
                  {(selectedStep.candidates?.length || 0) > 0 ? (
                    <div className="space-y-3 max-h-96 overflow-y-auto">
                      {selectedStep.candidates?.map((candidate, idx) => (
                        <div
                          key={idx}
                          className={`p-3 rounded border ${
                            candidate.decision === 'selected'
                              ? 'border-green-300 bg-green-50'
                              : candidate.decision === 'accepted'
                              ? 'border-blue-300 bg-blue-50'
                              : 'border-red-300 bg-red-50'
                          }`}
                        >
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs font-semibold uppercase text-gray-600">
                              {candidate.decision}
                            </span>
                            {candidate.candidate_id && (
                              <span className="text-xs text-gray-500">
                                ID: {candidate.candidate_id}
                              </span>
                            )}
                          </div>

                          {/* Attributes */}
                          {candidate.attributes && Object.keys(candidate.attributes).length > 0 && (
                            <div className="mb-2">
                              <div className="grid grid-cols-2 gap-2 text-xs">
                                {Object.entries(candidate.attributes).map(([key, value]) => (
                                  <div key={key}>
                                    <span className="text-gray-600">{key}:</span>{' '}
                                    <span className="text-gray-900 font-medium">
                                      {JSON.stringify(value)}
                                    </span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Score */}
                          {candidate.score && Object.keys(candidate.score).length > 0 && (
                            <div className="mb-2 flex gap-2 flex-wrap">
                              {Object.entries(candidate.score).map(([key, value]) => (
                                <span
                                  key={key}
                                  className="text-xs bg-white px-2 py-1 rounded border border-gray-200"
                                >
                                  {key}: {typeof value === 'number' ? value.toFixed(2) : value}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Reasoning */}
                          {candidate.reasoning && (
                            <p className="text-xs text-gray-700 italic mt-2">
                              {candidate.reasoning}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-gray-600">No candidates recorded for this step</p>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white rounded-lg shadow-sm p-12 text-center">
                <p className="text-gray-600">Select a step to view details</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
