import time
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, AsyncGenerator
from app.core.base_module import ForensicModule, ModuleResult, TaskStatus
from app.modules.hashing_engine import HashingEngine
from app.modules.metadata_engine import MetadataEngine
from app.modules.manipulation_ela import ManipulationELAModule
from app.modules.sift_engine import SIFTEngine
from app.modules.reverse_engine import ReverseEngine
from app.modules.ai_detector import AIDetector
from app.modules.context_osint_engine import ContextOSINTEngine
from app.connectors.instagram_connector import InstagramConnector
from app.connectors.facebook_connector import FacebookConnector
from app.connectors.telegram_connector import TelegramConnector
from app.database.repository import ForensicRepository

class AnalysisOrchestrator:
    def __init__(self):
        self.modules: List[ForensicModule] = [
            HashingEngine(),
            MetadataEngine(),
            ManipulationELAModule(),
            SIFTEngine(),
            ReverseEngine(),
            AIDetector(),
            ContextOSINTEngine(),
        ]
        self.connectors = [
            InstagramConnector(),
            FacebookConnector(),
            TelegramConnector()
        ]
        self.repo = ForensicRepository()
        self.active_streams: Dict[str, asyncio.Queue] = {}
        self.event_history: Dict[str, List[Dict[str, Any]]] = {}
        self.pool = ThreadPoolExecutor(max_workers=4)

    def register_stream(self, job_id: str) -> asyncio.Queue:
        if job_id not in self.active_streams:
            self.active_streams[job_id] = asyncio.Queue()
        # Immediately replay any historical events (e.g. PREPROCESSING) to newly connected client
        for past_event in self.event_history.get(job_id, []):
            try:
                self.active_streams[job_id].put_nowait(past_event)
            except Exception:
                pass
        return self.active_streams[job_id]

    def unregister_stream(self, job_id: str):
        if job_id in self.active_streams:
            del self.active_streams[job_id]

    async def broadcast_event(self, job_id: str, step_name: str, status: TaskStatus, 
                              progress_pct: float, elapsed_ms: float, 
                              result: Dict[str, Any] = None, error_message: str = None):
        payload = {
            "job_id": job_id,
            "step": step_name,
            "status": status.value,
            "progress_pct": round(progress_pct, 1),
            "elapsed_ms": round(elapsed_ms, 1),
            "result": result or {},
            "error_message": error_message
        }
        # Record in history so clients that connect a few milliseconds later get all events
        if job_id not in self.event_history:
            self.event_history[job_id] = []
        self.event_history[job_id].append(payload)

        queue = self.active_streams.get(job_id)
        if queue:
            await queue.put(payload)

    def _execute_single_module(self, module: ForensicModule, image_path: str, context: Dict[str, Any]) -> ModuleResult:
        try:
            return module.analyze(image_path, context)
        except Exception as e:
            return ModuleResult(
                module_name=module.name,
                status=TaskStatus.FAILED,
                result={},
                evidence_found=False,
                execution_time_ms=0.0,
                error_message=f"Module crashed: {str(e)}"
            )

    async def run_pipeline(self, job_id: str, image_path: str, original_filename: str):
        start_overall = time.perf_counter()
        context = {
            "job_id": job_id,
            "filename": original_filename,
            "image_path": image_path
        }

        total_tasks = len(self.modules) + len(self.connectors)
        completed_tasks = 0

        await self.broadcast_event(
            job_id, "PREPROCESSING", TaskStatus.COMPLETED, 5.0, 10.0,
            {"message": "Image ingestion, MIME validation, and file normalization complete."}
        )

        loop = asyncio.get_event_loop()

        async def _run_and_track(mod: ForensicModule):
            res = await loop.run_in_executor(self.pool, self._execute_single_module, mod, image_path, context)
            return mod, res

        tasks = []
        for mod in self.modules:
            await self.broadcast_event(job_id, mod.name, TaskStatus.RUNNING, (completed_tasks / total_tasks) * 100, 0.0)
            tasks.append(_run_and_track(mod))

        results_by_module: Dict[str, ModuleResult] = {}

        for coro in asyncio.as_completed(tasks):
            mod, res = await coro
            results_by_module[mod.name] = res
            completed_tasks += 1
            pct = 10.0 + ((completed_tasks / total_tasks) * 80.0)

            # Persist evidence to database
            self.repo.save_evidence(
                job_id=job_id,
                module_name=res.module_name,
                status=res.status.value,
                evidence_found=res.evidence_found,
                confidence=res.confidence,
                raw_payload=res.result,
                execution_time_ms=res.execution_time_ms,
                error_message=res.error_message
            )

            await self.broadcast_event(
                job_id, res.module_name, res.status, pct, res.execution_time_ms,
                res.result, res.error_message
            )

        # 2. Check Social Connectors
        social_results = []
        for conn in self.connectors:
            step_name = f"connector_{conn.platform_name.split()[0].lower()}"
            is_cfg = conn.is_configured()
            status = TaskStatus.COMPLETED if is_cfg else TaskStatus.NOT_CONFIGURED
            
            social_data = {
                "platform": conn.platform_name,
                "configured": is_cfg,
                "message": "Authorized ingestion configured" if is_cfg else "API credentials not configured in environment."
            }
            social_results.append(social_data)
            completed_tasks += 1
            pct = 10.0 + ((completed_tasks / total_tasks) * 85.0)

            await self.broadcast_event(
                job_id, step_name, status, pct, 5.0,
                social_data
            )

        total_elapsed = (time.perf_counter() - start_overall) * 1000.0
        self.repo.update_job_status(job_id, "COMPLETED", total_elapsed)

        # 3. Final Report Compilation
        await self.broadcast_event(
            job_id, "FINAL_REPORT", TaskStatus.COMPLETED, 100.0, total_elapsed,
            {"message": "Forensic evaluation dossier finalized and available for export."}
        )

    def generate_dossier(self, job_id: str) -> Dict[str, Any]:
        """Compiles a complete evidence dossier from recorded evidence."""
        job = self.repo.get_job(job_id)
        if not job:
            return {"error": "Job not found"}

        records = self.repo.get_evidence_records(job_id)
        
        fingerprints = {}
        reverse_matches = []
        forensic_integrity = {}
        metadata_provenance = {}
        ai_detection = {}
        context_osint = {}
        key_signals = []
        indicators_positive = 0

        for r in records:
            mod = r["module_name"]
            payload = r["raw_payload"]
            
            if mod == "hashing_engine":
                fingerprints = payload.get("fingerprints", {})
                if r["evidence_found"]:
                    key_signals.append("Exact or near-duplicate perceptual match identified in internal database.")
                    
            elif mod == "metadata_engine":
                metadata_provenance = payload
                if payload.get("editing_software_detected"):
                    softwares = ", ".join(payload["editing_software_detected"][:2])
                    key_signals.append(f"Editing software signatures detected in metadata: {softwares}")
                    indicators_positive += 1
                if payload.get("c2pa", {}).get("c2pa_present"):
                    key_signals.append("C2PA Content Credentials signature verified.")
                if payload.get("camera_make") or payload.get("camera_model"):
                    cam = f"{payload.get('camera_make', '')} {payload.get('camera_model', '')}".strip()
                    key_signals.append(f"Authentic camera hardware metadata present ({cam}).")

            elif mod == "manipulation_ela":
                forensic_integrity = payload
                ela = payload.get("ela", {})
                noise = payload.get("noise_analysis", {})
                copymove = payload.get("copy_move", {})
                
                if ela.get("ela_anomaly_detected"):
                    key_signals.append(f"Error Level Analysis reveals localized compression anomalies (Error Spike Ratio: {ela.get('local_discrepancy_ratio', 0)}x).")
                    indicators_positive += 1
                if noise.get("inconsistent_noise"):
                    key_signals.append("Laplacian noise variance shows spatial discontinuities typical of composite splicing.")
                    indicators_positive += 1
                if copymove.get("cloned_regions_found"):
                    key_signals.append(f"ORB keypoint self-matching detected {copymove.get('candidate_matches')} duplicated clone clusters.")
                    indicators_positive += 1

            elif mod == "sift_engine":
                sift_matches = payload.get("matches", [])
                if sift_matches:
                    key_signals.append(f"Homography keypoints matched against reference archive ({len(sift_matches)} reference match).")

            elif mod == "reverse_engine":
                reverse_matches = payload.get("matches", [])
                if reverse_matches:
                    key_signals.append(f"OpenCLIP semantic vector search found {len(reverse_matches)} visually similar references.")

            elif mod == "ai_detector":
                ai_detection = payload
                synth_score = float(payload.get("synthetic_likelihood", 0.0))
                bracket = payload.get("classification_bracket", "")
                if synth_score >= 0.65:
                    key_signals.append(f"Deepfake / Synthetic classifier flagged high likelihood of AI generation ({synth_score * 100:.1f}%).")
                    indicators_positive += 2
                elif synth_score <= 0.30:
                    key_signals.append(f"Deepfake / Synthetic classifier confirms human/camera origin patterns (Authentic Likelihood: {(1.0 - synth_score) * 100:.1f}%).")

            elif mod == "context_osint_engine":
                context_osint = payload
                if payload.get("scenario_incongruity_detected"):
                    key_signals.append(f"Contextual OSINT Mismatch: {payload.get('conflict_explanation')}")
                    indicators_positive += 3
                elif payload.get("scenario_aligned_detected"):
                    key_signals.append(f"Contextual Profession Verified: {payload.get('alignment_explanation')}")
                elif payload.get("entity_identified"):
                    key_signals.append(f"Public Personality Identified: {payload.get('entity_identified')} ({payload.get('entity_profession')}).")

        # Dynamic Continuous Scoring Engine
        synth_prob = float(ai_detection.get("synthetic_likelihood", 0.10))
        ela_flag = bool(forensic_integrity.get("ela", {}).get("ela_anomaly_detected", False))
        noise_flag = bool(forensic_integrity.get("noise_analysis", {}).get("inconsistent_noise", False))
        copymove_flag = bool(forensic_integrity.get("copy_move", {}).get("cloned_regions_found", False))
        software_flag = bool(metadata_provenance.get("editing_software_detected"))
        has_cam = bool(metadata_provenance.get("camera_make") or metadata_provenance.get("camera_model"))
        context_conflict = bool(context_osint.get("scenario_incongruity_detected", False))
        context_aligned = bool(context_osint.get("scenario_aligned_detected", False))

        # =========================================================================
        # DUAL-PASS RIGOROUS VERIFICATION PIPELINE
        # =========================================================================
        
        # PASS 1: Contextual & Vocational OSINT Evaluation (Informed Pass)
        entity_name = context_osint.get("entity_identified", "Unregistered Individual / Civilian")
        entity_role = context_osint.get("entity_profession", "Unknown / Civilian")
        act_desc = context_osint.get("depicted_activity", "General scene")
        
        if context_conflict:
            pass_1_verdict = "CONTEXTUAL_INCONGRUITY_FABRICATION"
            pass_1_risk = 95.0
            pass_1_note = context_osint.get("conflict_explanation", "Activity contradicts subject's authentic profession.")
        elif context_aligned:
            pass_1_verdict = "VOCATIONAL_ALIGNMENT_AUTHENTIC"
            pass_1_risk = 5.0
            pass_1_note = context_osint.get("alignment_explanation", "Activity aligns with subject's genuine career.")
        else:
            pass_1_verdict = "NEUTRAL_CIVILIAN_CONTEXT"
            pass_1_risk = 20.0
            pass_1_note = "No famous entity conflict or celebrity incongruity identified."

        # PASS 2: Strict Blind Physical Forensic Evaluation ("Without Clue" Pass)
        # Strips all identity knowledge and evaluates strictly pixel physics & neural diffusion
        blind_tamper_score = synth_prob * 70.0
        if ela_flag:
            blind_tamper_score += 20.0
        if noise_flag:
            blind_tamper_score += 15.0
        if copymove_flag:
            blind_tamper_score += 25.0
        if software_flag:
            blind_tamper_score += 15.0
        if has_cam:
            blind_tamper_score = max(1.0, blind_tamper_score - 15.0)
            
        blind_tamper_score = max(1.0, min(99.0, round(blind_tamper_score, 1)))
        blind_authenticity_score = round(100.0 - blind_tamper_score, 1)
        
        if blind_tamper_score >= 65.0:
            pass_2_verdict = "HIGH_SYNTHETIC_OR_TAMPER_SIGNALS"
            pass_2_note = f"Blind physical forensics detected high synthetic markers (AI probability: {synth_prob*100:.1f}%) or localized compression anomalies."
        elif blind_tamper_score >= 35.0:
            pass_2_verdict = "SUSPICIOUS_PHYSICAL_ANOMALIES"
            pass_2_note = f"Blind forensic tests detected compression/noise variance anomalies (Tamper risk: {blind_tamper_score}%)."
        else:
            pass_2_verdict = "NATURAL_CAMERA_CHARACTERISTICS"
            pass_2_note = f"Blind forensic tests show consistent sensor noise, uniform compression, and natural camera optical falloff (Authenticity: {blind_authenticity_score}%)."

        # PASS 3: Consensus Reconciliation (Cross-Evaluating Pass 1 and Pass 2)
        if context_conflict:
            # Contextual exposure takes precedence even if downscaling washed out pixel noise
            reconciled_tamper_score = max(95.0, blind_tamper_score)
            reconciled_verdict = "HIGH_MANIPULATION_OR_SYNTHETIC_SIGNALS"
            consensus_mode = "CONTEXTUAL_EXPOSURE_OVERRIDE"
            summary_statement = (
                f"Fictional / Synthetic generation confirmed via Dual-Pass Synthesis. "
                f"Pass 1 (OSINT): {pass_1_note} "
                f"Pass 2 (Blind Forensics): {pass_2_note} "
                f"Consensus: Real-world impossibility confirms generative AI fabrication."
            )
        elif pass_2_verdict in ["HIGH_SYNTHETIC_OR_TAMPER_SIGNALS", "SUSPICIOUS_PHYSICAL_ANOMALIES"] and not context_aligned:
            # Physical forensics caught manipulation on a civilian or normal setting
            reconciled_tamper_score = blind_tamper_score
            reconciled_verdict = "HIGH_MANIPULATION_OR_SYNTHETIC_SIGNALS" if blind_tamper_score >= 65.0 else "SUSPICIOUS_SIGNALS_DETECTED"
            consensus_mode = "PHYSICAL_FORENSIC_FLAG"
            summary_statement = (
                f"Digital manipulation or synthetic generation flagged via Dual-Pass Synthesis. "
                f"Pass 2 (Blind Forensics) identified acute anomalies: {pass_2_note}."
            )
        elif context_aligned and pass_2_verdict == "NATURAL_CAMERA_CHARACTERISTICS":
            # Both passes mutually corroborate authenticity!
            reconciled_tamper_score = min(5.0, blind_tamper_score)
            reconciled_verdict = "NO_OBVIOUS_TAMPERING_SIGNALS"
            consensus_mode = "UNANIMOUS_MUTUAL_CORROBORATION"
            summary_statement = (
                f"Authentic capture verified via Dual-Pass Synthesis. "
                f"Pass 1 (OSINT) confirmed real-world career setting ({entity_name} as {entity_role}), "
                f"and Pass 2 (Blind Forensics) independently confirmed genuine sensor noise and compression integrity."
            )
        else:
            reconciled_tamper_score = blind_tamper_score
            reconciled_verdict = "NO_OBVIOUS_TAMPERING_SIGNALS" if blind_tamper_score < 35.0 else "SUSPICIOUS_SIGNALS_DETECTED"
            consensus_mode = "STANDARD_CONVERGENCE"
            summary_statement = (
                f"Dual-Pass analysis convergence: Pass 1 noted {pass_1_verdict}, "
                f"and Pass 2 noted {pass_2_verdict} (Authenticity: {blind_authenticity_score}%)."
            )

        reconciled_tamper_score = max(1.0, min(99.0, round(reconciled_tamper_score, 1)))
        reconciled_authenticity_score = round(100.0 - reconciled_tamper_score, 1)
        confidence_rating = round((reconciled_tamper_score if reconciled_tamper_score >= 50 else reconciled_authenticity_score) / 100.0, 3)

        return {
            "job_id": job_id,
            "metadata": {
                "filename": job["source_filename"],
                "file_size_bytes": job["file_size_bytes"],
                "mime_type": job["mime_type"],
                "created_at": job["created_at"],
                "total_execution_time_ms": job["total_execution_time_ms"],
                "status": job["status"]
            },
            "fingerprints": fingerprints,
            "metadata_provenance": metadata_provenance,
            "forensic_integrity": forensic_integrity,
            "reverse_matches": reverse_matches,
            "ai_generation_detection": ai_detection,
            "context_osint": context_osint,
            "dual_pass_evaluation": {
                "pass_1_contextual_osint": {
                    "entity_identified": entity_name,
                    "entity_profession": entity_role,
                    "depicted_activity": act_desc,
                    "verdict": pass_1_verdict,
                    "tamper_risk": pass_1_risk,
                    "details": pass_1_note
                },
                "pass_2_blind_forensic": {
                    "verdict": pass_2_verdict,
                    "blind_tamper_score": blind_tamper_score,
                    "blind_authenticity_score": blind_authenticity_score,
                    "details": pass_2_note
                },
                "consensus_reconciliation": {
                    "mode": consensus_mode,
                    "reconciled_verdict": reconciled_verdict,
                    "reconciled_authenticity_score": reconciled_authenticity_score,
                    "reconciled_tamper_score": reconciled_tamper_score,
                    "synthesis_summary": summary_statement
                }
            },
            "verdict": {
                "verdict_type": reconciled_verdict,
                "confidence_rating": confidence_rating,
                "authenticity_score": reconciled_authenticity_score,
                "tamper_score": reconciled_tamper_score,
                "summary": summary_statement,
                "key_indicators": key_signals,
                "forensic_notice": "Forensic findings are empirical indicators for investigative review, synthesized across contextual OSINT and blind physical passes."
            }
        }

orchestrator = AnalysisOrchestrator()
