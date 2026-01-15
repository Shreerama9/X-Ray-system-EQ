'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  fetchRuns,
  fetchSteps,
  fetchCandidates,
  fetchStats,
  Run,
  Step,
  Candidate,
  Stats,
} from '@/lib/api';

type TabType = 'runs' | 'steps' | 'candidates';

export default function DatabaseExplorer() {
  const [activeTab, setActiveTab] = useState<TabType>('runs');
  const [runs, setRuns] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Step[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Filters
  const [runFilter, setRunFilter] = useState({ pipeline_type: '', status: '' });
  const [stepFilter, setStepFilter] = useState({ step_type: '', status: '' });
  const [candidateFilter, setCandidateFilter] = useState({ decision: '' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [runsData, stepsData, candidatesData, statsData] = await Promise.all([
        fetchRuns({ limit: 100 }),
        fetchSteps({ limit: 100 }),
        fetchCandidates({ limit: 100 }),
        fetchStats(),
      ]);

      setRuns(runsData);
      setSteps(stepsData);
      setCandidates(candidatesData);
      setStats(statsData);
      setLastUpdated(new Date());
    } catch (err) {
      setError('Failed to load data. Make sure the API server is running on port 8000.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(loadData, 3000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, loadData]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const filteredRuns = runs.filter((run) => {
    if (runFilter.pipeline_type && !run.pipeline_type.toLowerCase().includes(runFilter.pipeline_type.toLowerCase())) {
      return false;
    }
    if (runFilter.status && run.status !== runFilter.status) {
      return false;
    }
    return true;
  });

  const filteredSteps = steps.filter((step) => {
    if (stepFilter.step_type && step.step_type !== stepFilter.step_type) {
      return false;
    }
    if (stepFilter.status && step.status !== stepFilter.status) {
      return false;
    }
    return true;
  });

  const filteredCandidates = candidates.filter((candidate) => {
    if (candidateFilter.decision && candidate.decision !== candidateFilter.decision) {
      return false;
    }
    return true;
  });

  const tabs: { id: TabType; label: string; count: number }[] = [
    { id: 'runs', label: 'Runs', count: runs.length },
    { id: 'steps', label: 'Steps', count: steps.length },
    { id: 'candidates', label: 'Candidates', count: candidates.length },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <div className="mb-6 flex justify-between items-start">
          <div>
            <h1 className="text-3xl font-light text-gray-900 mb-2">Database Explorer</h1>
            <p className="text-gray-600">View all data from the X-Ray database</p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-gray-600">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              Auto-refresh (3s)
            </label>
            <button
              onClick={loadData}
              disabled={loading}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Loading...' : 'Refresh'}
            </button>
          </div>
        </div>

        {/* Last Updated */}
        {lastUpdated && (
          <p className="text-xs text-gray-500 mb-4">
            Last updated: {lastUpdated.toLocaleString()}
          </p>
        )}

        {/* Stats Overview */}
        {stats && (
          <div className="mb-6 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Total Runs</p>
              <p className="text-2xl font-light text-gray-900">{stats.runs.total}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Successful Runs</p>
              <p className="text-2xl font-light text-green-600">{stats.runs.successful}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Failed Runs</p>
              <p className="text-2xl font-light text-red-600">{stats.runs.failed}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Total Steps</p>
              <p className="text-2xl font-light text-gray-900">{stats.steps.total}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Total Candidates</p>
              <p className="text-2xl font-light text-gray-900">{stats.candidates.total}</p>
            </div>
            <div className="bg-white p-4 rounded-lg shadow-sm">
              <p className="text-xs text-gray-600">Pipeline Types</p>
              <p className="text-2xl font-light text-blue-600">{stats.pipeline_types}</p>
            </div>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Tabs */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="border-b border-gray-200">
            <nav className="flex -mb-px">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  {tab.label}
                  <span className="ml-2 px-2 py-0.5 text-xs bg-gray-100 rounded-full">
                    {tab.count}
                  </span>
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {/* Runs Tab */}
            {activeTab === 'runs' && (
              <div>
                {/* Filters */}
                <div className="mb-4 flex gap-4">
                  <input
                    type="text"
                    placeholder="Filter by pipeline type..."
                    value={runFilter.pipeline_type}
                    onChange={(e) => setRunFilter({ ...runFilter, pipeline_type: e.target.value })}
                    className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                  <select
                    value={runFilter.status}
                    onChange={(e) => setRunFilter({ ...runFilter, status: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Statuses</option>
                    <option value="SUCCESS">SUCCESS</option>
                    <option value="FAILURE">FAILURE</option>
                    <option value="RUNNING">RUNNING</option>
                  </select>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Pipeline Type</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Started At</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Steps</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Metadata</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredRuns.map((run) => (
                        <tr key={run.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs font-mono text-gray-600">
                            {run.id.substring(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{run.pipeline_type}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                                run.status === 'SUCCESS'
                                  ? 'bg-green-100 text-green-800'
                                  : run.status === 'FAILURE'
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-yellow-100 text-yellow-800'
                              }`}
                            >
                              {run.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-600">{formatDate(run.started_at)}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{run.steps?.length || 0}</td>
                          <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                            {run.metadata ? JSON.stringify(run.metadata) : '-'}
                          </td>
                          <td className="px-4 py-3">
                            <Link
                              href={`/run/${run.id}`}
                              className="text-blue-600 hover:text-blue-800 text-sm"
                            >
                              View
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredRuns.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No runs found</div>
                  )}
                </div>
              </div>
            )}

            {/* Steps Tab */}
            {activeTab === 'steps' && (
              <div>
                {/* Filters */}
                <div className="mb-4 flex gap-4">
                  <select
                    value={stepFilter.step_type}
                    onChange={(e) => setStepFilter({ ...stepFilter, step_type: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Step Types</option>
                    <option value="LLM">LLM</option>
                    <option value="FILTER">FILTER</option>
                    <option value="API">API</option>
                    <option value="RANKING">RANKING</option>
                  </select>
                  <select
                    value={stepFilter.status}
                    onChange={(e) => setStepFilter({ ...stepFilter, status: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Statuses</option>
                    <option value="SUCCESS">SUCCESS</option>
                    <option value="FAILURE">FAILURE</option>
                  </select>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Run ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Step Name</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Candidates</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stats</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredSteps.map((step) => (
                        <tr key={step.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs font-mono text-gray-600">
                            {step.id.substring(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-xs font-mono text-gray-500">
                            <Link href={`/run/${step.run_id}`} className="text-blue-600 hover:text-blue-800">
                              {step.run_id.substring(0, 8)}...
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{step.step_name}</td>
                          <td className="px-4 py-3">
                            <span className="px-2 py-0.5 text-xs bg-gray-100 rounded">{step.step_type}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                                step.status === 'SUCCESS'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {step.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-600">{formatDuration(step.duration_ms)}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{step.candidates?.length || 0}</td>
                          <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                            {step.stats ? JSON.stringify(step.stats) : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredSteps.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No steps found</div>
                  )}
                </div>
              </div>
            )}

            {/* Candidates Tab */}
            {activeTab === 'candidates' && (
              <div>
                {/* Filters */}
                <div className="mb-4 flex gap-4">
                  <select
                    value={candidateFilter.decision}
                    onChange={(e) => setCandidateFilter({ ...candidateFilter, decision: e.target.value })}
                    className="px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Decisions</option>
                    <option value="selected">Selected</option>
                    <option value="accepted">Accepted</option>
                    <option value="rejected">Rejected</option>
                  </select>
                </div>

                {/* Table */}
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Step ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Candidate ID</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Decision</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Score</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Attributes</th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Reasoning</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredCandidates.map((candidate) => (
                        <tr key={candidate.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-xs font-mono text-gray-600">
                            {candidate.id.substring(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-xs font-mono text-gray-500">
                            {candidate.step_id.substring(0, 8)}...
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-900">{candidate.candidate_id}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                                candidate.decision === 'selected'
                                  ? 'bg-green-100 text-green-800'
                                  : candidate.decision === 'accepted'
                                  ? 'bg-blue-100 text-blue-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {candidate.decision}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-500">
                            {candidate.score ? JSON.stringify(candidate.score) : '-'}
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                            {candidate.attributes ? JSON.stringify(candidate.attributes) : '-'}
                          </td>
                          <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                            {candidate.reasoning || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filteredCandidates.length === 0 && (
                    <div className="text-center py-8 text-gray-500">No candidates found</div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
