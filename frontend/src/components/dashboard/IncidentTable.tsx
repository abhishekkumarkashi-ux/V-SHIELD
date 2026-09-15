export interface IncidentTableProps {
  history: any[];
}

const IncidentTable = ({ history }: IncidentTableProps) => {
  // Map history to incidents (top 5 highest risk)
  const incidents = history
    .slice()
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 5)
    .map((h, i) => ({
      id: h.id || i,
      desk: h.target_desk || 'Unknown',
      type: h.spoof_probability > 0.7 ? 'Voice Clone' : h.risk_score > 0.7 ? 'High Risk' : 'Suspicious',
      risk: Math.round(h.risk_score * 100),
      status: h.risk_level === 'CRITICAL' ? 'BLOCKED' : h.risk_level === 'HIGH' ? 'REVIEW' : 'MITIGATED'
    }));


  return (
    <div className="bg-surface-container rounded border border-outline-variant p-5 flex flex-col">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="font-headline-sm text-on-surface text-sm font-semibold">Recent Security Incidents</h3>
          <p className="font-body-sm text-[11px] text-outline mt-1">Latest voice security events requiring attention.</p>
        </div>
        <div className="flex items-center gap-2 font-label-sm text-[10px] text-outline">
          SORT BY: <span className="text-primary cursor-pointer hover:underline">Highest Risk</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-outline-variant/50">
              <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">INCIDENT</th>
              <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">TYPE</th>
              <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider">RISK</th>
              <th className="py-2 px-3 font-label-sm text-[10px] text-outline font-normal uppercase tracking-wider text-right">STATUS</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-outline-variant/30">
            {incidents.map((incident) => (
              <tr key={incident.id} className="hover:bg-surface-container-high transition-colors">
                <td className="py-3 px-3 font-body-sm text-xs text-on-surface">{incident.desk}</td>
                <td className="py-3 px-3">
                  <span className="font-label-sm text-[10px] text-error bg-error/10 border border-error/20 px-2 py-0.5 rounded">
                    {incident.type}
                  </span>
                </td>
                <td className="py-3 px-3">
                  <div className="flex items-center gap-1 font-code-md text-[11px]">
                    <span className={incident.risk > 80 ? 'text-error' : incident.risk > 70 ? 'text-orange-400' : 'text-yellow-400'}>
                      {incident.risk}
                    </span>
                    <span className="text-outline">/100</span>
                  </div>
                </td>
                <td className="py-3 px-3 text-right">
                  <span className={`font-label-sm text-[9px] tracking-widest px-2 py-0.5 rounded border ${
                    incident.status === 'MITIGATED' ? 'bg-error/10 text-error border-error/20' :
                    incident.status === 'BLOCKED' ? 'bg-primary/10 text-primary border-primary/20' :
                    'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                  }`}>
                    {incident.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default IncidentTable;
