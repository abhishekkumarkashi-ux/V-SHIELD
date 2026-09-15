import { Users, Target, Activity, ShieldCheck, Search, Plus, Settings, RefreshCw, UserCheck, ShieldAlert, Sliders } from 'lucide-react';

const SpeakerVerification = () => {
  return (
    <div className="flex flex-col w-full h-full gap-4">
      {/* Header Section */}
      <div className="flex flex-col gap-4 border-b border-outline-variant/50 pb-5">
        <div className="flex justify-between items-start">
          <div className="flex flex-col gap-1">
            <span className="font-code-sm text-[10px] text-primary tracking-widest uppercase font-bold">
              BIOMETRIC IDENTITY ACCESS MANAGEMENT
            </span>
            <h1 className="font-headline-xl text-3xl text-on-surface tracking-tight font-semibold mt-1">Speaker Verification</h1>
            <p className="font-body-sm text-sm text-outline mt-1">Manage executive voiceprints and configure biometric multi-factor authentication (MFA) thresholds.</p>
          </div>
          <div className="flex flex-col gap-3 items-end">
            <div className="flex items-center gap-3">
              <button className="flex items-center gap-2 px-4 py-1.5 border border-[#45e0a0]/50 text-[#45e0a0] bg-[#45e0a0]/10 hover:bg-[#45e0a0]/20 transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
                <Plus className="w-3.5 h-3.5" /> Enroll New Speaker
              </button>
              <button className="flex items-center gap-2 px-4 py-1.5 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
                <Settings className="w-3.5 h-3.5" /> Manage Access Tiers
              </button>
              <button className="flex items-center gap-2 px-4 py-1.5 border border-outline-variant text-on-surface hover:bg-surface-container-high transition-colors rounded font-label-sm text-[11px] uppercase tracking-wider font-bold">
                <RefreshCw className="w-3.5 h-3.5" /> Refresh Profiles
              </button>
            </div>
            <div className="relative w-64">
               <Search className="w-4 h-4 text-outline absolute left-3 top-1/2 -translate-y-1/2" />
               <input 
                 type="text" 
                 placeholder="Search profiles..." 
                 className="w-full bg-[#0f172a] border border-outline-variant rounded py-1.5 pl-9 pr-3 text-sm text-on-surface focus:outline-none focus:border-primary placeholder-outline/50"
               />
            </div>
          </div>
        </div>

        {/* 4 Metrics */}
        <div className="grid grid-cols-4 gap-4 mt-2">
          {/* Card 1 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">ENROLLED PROFILES</span>
              <Users className="w-4 h-4 text-[#00c8e8]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">24</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-label-sm text-[10px] text-outline"><span className="text-[#00c8e8] font-bold">2</span> pending verification</span>
              </div>
            </div>
          </div>
          {/* Card 2 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">VERIFICATION SUCCESS RATE</span>
              <Target className="w-4 h-4 text-[#45e0a0]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-[#45e0a0] leading-none">98.4%</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-label-sm text-[10px] text-outline">Last 30 days</span>
              </div>
            </div>
          </div>
          {/* Card 3 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">ACTIVE LIVENESS CHALLENGES</span>
              <Activity className="w-4 h-4 text-[#ffaaa0]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[2.5rem] font-headline-sm font-bold tracking-tight text-on-surface leading-none">3</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <div className="w-1.5 h-1.5 rounded-full bg-[#ffaaa0] animate-pulse" />
                <span className="font-label-sm text-[10px] text-outline">In progress</span>
              </div>
            </div>
          </div>
          {/* Card 4 */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-4 flex flex-col justify-between shadow-lg h-28">
            <div className="flex justify-between items-start">
              <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest font-bold">BIOMETRIC MFA STATUS</span>
              <ShieldCheck className="w-4 h-4 text-[#45e0a0]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-baseline gap-1 mt-1">
                <span className="text-[1.8rem] font-headline-sm font-bold tracking-tight text-[#45e0a0] leading-none">ENFORCED</span>
              </div>
              <div className="flex items-center gap-2 mt-2">
                <span className="font-label-sm text-[10px] text-outline">Tier 1 & 2 Accounts</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 mt-2">
        {/* Left Column: Profiles */}
        <div className="flex flex-col">
          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
             <div className="flex justify-between items-center mb-2">
               <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Enrolled Executive Voice Profiles</h3>
               <span className="font-label-sm text-[10px] text-outline font-bold">4 Profiles Found</span>
             </div>
             
             <div className="flex flex-col gap-3">
               {/* Profile 1 */}
               <div className="border border-outline-variant rounded p-4 bg-surface-container-lowest flex items-start gap-4">
                  <div className="w-10 h-10 rounded bg-[#00c8e8]/20 flex items-center justify-center font-bold text-[#00c8e8] text-lg border border-[#00c8e8]/30">JS</div>
                  <div className="flex flex-col flex-1 gap-1">
                    <div className="flex justify-between items-start">
                       <div>
                         <span className="font-body-sm text-sm text-on-surface font-bold block">J. Smith</span>
                         <span className="font-label-sm text-[11px] text-outline">Chief Financial Officer</span>
                       </div>
                       <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">ACTIVE</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">PROFILE MATCH CONFIDENCE</span>
                         <span className="font-code-sm text-[#00c8e8] font-bold">98%</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">SAMPLES</span>
                         <span className="font-code-sm text-on-surface">48 audio</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LAST SYNC</span>
                         <span className="font-code-sm text-on-surface">2 hours ago</span>
                       </div>
                    </div>
                  </div>
               </div>

               {/* Profile 2 */}
               <div className="border border-outline-variant rounded p-4 bg-surface-container-lowest flex items-start gap-4">
                  <div className="w-10 h-10 rounded bg-[#45e0a0]/20 flex items-center justify-center font-bold text-[#45e0a0] text-lg border border-[#45e0a0]/30">MC</div>
                  <div className="flex flex-col flex-1 gap-1">
                    <div className="flex justify-between items-start">
                       <div>
                         <span className="font-body-sm text-sm text-on-surface font-bold block">M. Chen</span>
                         <span className="font-label-sm text-[11px] text-outline">VP of Operations</span>
                       </div>
                       <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">ACTIVE</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">PROFILE MATCH CONFIDENCE</span>
                         <span className="font-code-sm text-[#00c8e8] font-bold">95%</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">SAMPLES</span>
                         <span className="font-code-sm text-on-surface">32 audio</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LAST SYNC</span>
                         <span className="font-code-sm text-on-surface">1 day ago</span>
                       </div>
                    </div>
                  </div>
               </div>

               {/* Profile 3 */}
               <div className="border border-outline-variant/50 rounded p-4 bg-surface-container-lowest/50 flex items-start gap-4 opacity-75">
                  <div className="w-10 h-10 rounded bg-[#facc15]/20 flex items-center justify-center font-bold text-[#facc15] text-lg border border-[#facc15]/30">AD</div>
                  <div className="flex flex-col flex-1 gap-1">
                    <div className="flex justify-between items-start">
                       <div>
                         <span className="font-body-sm text-sm text-on-surface font-bold block">A. Davis</span>
                         <span className="font-label-sm text-[11px] text-outline">Head of Treasury</span>
                       </div>
                       <span className="px-2 py-0.5 bg-[#facc15]/10 text-[#facc15] border border-[#facc15]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">PENDING CALIBRATION</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">PROFILE MATCH CONFIDENCE</span>
                         <span className="font-code-sm text-[#facc15] font-bold">--</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">SAMPLES</span>
                         <span className="font-code-sm text-on-surface">14 audio</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">STATUS</span>
                         <span className="font-code-sm text-[#facc15]">Needs more data</span>
                       </div>
                    </div>
                  </div>
               </div>

               {/* Profile 4 */}
               <div className="border border-outline-variant rounded p-4 bg-surface-container-lowest flex items-start gap-4">
                  <div className="w-10 h-10 rounded bg-[#a78bfa]/20 flex items-center justify-center font-bold text-[#a78bfa] text-lg border border-[#a78bfa]/30">EW</div>
                  <div className="flex flex-col flex-1 gap-1">
                    <div className="flex justify-between items-start">
                       <div>
                         <span className="font-body-sm text-sm text-on-surface font-bold block">E. Wilson</span>
                         <span className="font-label-sm text-[11px] text-outline">CEO</span>
                       </div>
                       <span className="px-2 py-0.5 bg-[#45e0a0]/10 text-[#45e0a0] border border-[#45e0a0]/20 font-label-sm text-[10px] tracking-widest font-bold rounded">ACTIVE</span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 mt-2">
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">PROFILE MATCH CONFIDENCE</span>
                         <span className="font-code-sm text-[#00c8e8] font-bold">99%</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">SAMPLES</span>
                         <span className="font-code-sm text-on-surface">105 audio</span>
                       </div>
                       <div className="flex flex-col">
                         <span className="font-label-sm text-[9px] text-outline uppercase tracking-widest">LAST SYNC</span>
                         <span className="font-code-sm text-on-surface">4 hours ago</span>
                       </div>
                    </div>
                  </div>
               </div>

             </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="flex flex-col gap-5">
          {/* Verification Event Log */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
            <h3 className="font-headline-sm text-lg text-on-surface font-semibold mb-2">Verification Event Log</h3>
            <div className="flex flex-col gap-0">
               <div className="flex items-start gap-4 py-3 border-b border-outline-variant/50">
                 <div className="p-2 rounded-full bg-[#45e0a0]/10 border border-[#45e0a0]/20 mt-1"><UserCheck className="w-4 h-4 text-[#45e0a0]" /></div>
                 <div className="flex flex-col flex-1">
                   <div className="flex justify-between">
                     <span className="font-body-sm text-sm text-on-surface font-bold">J. Smith</span>
                     <span className="font-code-sm text-[10px] text-outline">10:42 AM</span>
                   </div>
                   <span className="font-body-sm text-[11px] text-outline">Authorized wire transfer approval</span>
                 </div>
               </div>
               
               <div className="flex items-start gap-4 py-3 border-b border-outline-variant/50">
                 <div className="p-2 rounded-full bg-error/10 border border-error/20 mt-1"><ShieldAlert className="w-4 h-4 text-error" /></div>
                 <div className="flex flex-col flex-1">
                   <div className="flex justify-between">
                     <span className="font-body-sm text-sm text-error font-bold">Unknown</span>
                     <span className="font-code-sm text-[10px] text-outline">09:15 AM</span>
                   </div>
                   <span className="font-body-sm text-[11px] text-outline">Impersonation attempt blocked (M. Chen)</span>
                 </div>
               </div>
               
               <div className="flex items-start gap-4 py-3">
                 <div className="p-2 rounded-full bg-[#45e0a0]/10 border border-[#45e0a0]/20 mt-1"><UserCheck className="w-4 h-4 text-[#45e0a0]" /></div>
                 <div className="flex flex-col flex-1">
                   <div className="flex justify-between">
                     <span className="font-body-sm text-sm text-on-surface font-bold">E. Wilson</span>
                     <span className="font-code-sm text-[10px] text-outline">Yesterday, 14:30</span>
                   </div>
                   <span className="font-body-sm text-[11px] text-outline">Authenticated board call entry</span>
                 </div>
               </div>
            </div>
          </div>

          {/* Configure Liveness Challenge */}
          <div className="bg-[#0f172a] border border-outline-variant rounded p-6 shadow-lg flex flex-col gap-4">
             <div className="flex justify-between items-start mb-2">
               <div className="flex flex-col gap-1">
                 <h3 className="font-headline-sm text-lg text-on-surface font-semibold">Configure Liveness Challenge</h3>
                 <span className="font-body-sm text-[11px] text-outline">Dynamic MFA phrase generation for high-risk transactions.</span>
               </div>
               <Sliders className="w-5 h-5 text-[#00c8e8]" />
             </div>

             <div className="flex flex-col gap-5 mt-2">
               <div className="flex flex-col gap-2">
                 <div className="flex justify-between font-label-sm text-[11px]">
                   <span className="text-on-surface">Challenge Complexity</span>
                   <span className="text-[#00c8e8] font-bold">High</span>
                 </div>
                 <input type="range" min="1" max="100" defaultValue="80" className="w-full accent-[#00c8e8]" />
               </div>

               <div className="flex flex-col gap-2">
                 <label className="font-label-sm text-[11px] text-on-surface">Phrase Expiration</label>
                 <select className="bg-[#1e293b] border border-outline-variant rounded p-2 text-sm text-on-surface outline-none focus:border-[#00c8e8]">
                   <option>15 seconds</option>
                   <option selected>30 seconds</option>
                   <option>60 seconds</option>
                 </select>
               </div>

               <div className="flex items-center justify-between py-2 border-b border-outline-variant/50">
                 <span className="font-label-sm text-[11px] text-on-surface">Require Video/Facial Sync</span>
                 <div className="w-8 h-4 bg-outline-variant rounded-full relative cursor-pointer">
                    <div className="w-3 h-3 bg-outline rounded-full absolute top-0.5 left-0.5"></div>
                 </div>
               </div>

               <div className="flex items-center justify-between py-2">
                 <span className="font-label-sm text-[11px] text-on-surface">Enforce Semantic Consistency</span>
                 <div className="w-8 h-4 bg-[#45e0a0]/30 rounded-full relative cursor-pointer border border-[#45e0a0]/50">
                    <div className="w-3 h-3 bg-[#45e0a0] rounded-full absolute top-0.5 right-0.5 shadow"></div>
                 </div>
               </div>
             </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default SpeakerVerification;
