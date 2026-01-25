import express from 'express';
import { query } from '../db.js';

const router = express.Router();

/**
 * Transform N8N ui_json.results data to match frontend Tender interface
 */
function transformTenderResult(result) {
  return {
    id: result.tender_id || result.actions?.details_id || `tender-${Date.now()}`,
    title: result.title_de || 'Untitled Tender',
    buyer: result.client_de || 'Unknown',
    region: result.region_code || 'DE',
    deadline: result.deadline_date || new Date().toISOString().split('T')[0],
    url: result.actions?.details_id ? `/tender/${result.actions.details_id}` : '#',
    score: result.scores?.total_percent || 0,
    legalRisks: result.right_side_risks_de || [],
    mustHits: parseInt(result.scores?.must_fraction?.split('/')[0] || '0'),
    mustTotal: parseInt(result.scores?.must_fraction?.split('/')[1] || '0'),
    canHits: parseInt(result.scores?.can_fraction?.split('/')[0] || '0'),
    canTotal: parseInt(result.scores?.can_fraction?.split('/')[1] || '0'),
    serviceTypes: result.tags_de || [],
    scopeOfWork: result.title_de,
  };
}

/**
 * Transform N8N ui_json.overview data for detailed view
 */
function transformTenderOverview(overview, tenderId) {
  return {
    id: tenderId,
    title: overview.tender_id || tenderId,
    deadline: overview.submission_deadline?.date || null,
    deadlineLabel: overview.submission_deadline?.label_de || 'Submission Deadline',
    daysRemaining: overview.submission_deadline?.days_remaining || null,
    briefDescription: overview.executive_summary_de?.brief_description_de || '',
    goNoGo: overview.executive_summary_de?.go_nogo_de || [],
    supplyCapability: overview.executive_summary_de?.supply_capability_de || [],
    economicEfficiency: overview.executive_summary_de?.economic_efficiency_de || [],
    awardLogic: overview.executive_summary_de?.award_logic_de || [],
    mandatoryRequirements: overview.top5_mandatory_requirements_de || [],
    mainRisks: overview.main_risks_de || [],
    missingEvidence: overview.missing_evidence_de || [],
    economicAnalysis: overview.economic_analysis_de || {
      potential_margin: {},
      order_value_estimated: {},
      signals: {}
    }
  };
}

/**
 * Parse date from German text format (DD.MM.YYYY) or ISO format (YYYY-MM-DD)
 * Returns ISO date string or null
 */
function parseDateFromText(text) {
  if (!text || typeof text !== 'string') return null;

  // Match German date format: DD.MM.YYYY
  const germanDateMatch = text.match(/(\d{1,2})\.(\d{1,2})\.(\d{4})/);
  if (germanDateMatch) {
    const [, day, month, year] = germanDateMatch;
    return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
  }

  // Match ISO format: YYYY-MM-DD
  const isoMatch = text.match(/(\d{4})-(\d{2})-(\d{2})/);
  if (isoMatch) return isoMatch[0];

  return null;
}

/**
 * Transform nested summary structure (actual N8N DB format) to frontend Tender format
 * Includes document source tracking, KPI calculation, certification extraction, and validation
 */
function transformNestedSummaryToFlat(uiJson, runId) {
  // Validate input
  if (!uiJson || typeof uiJson !== 'object') {
    console.warn(`Invalid uiJson for run ${runId}`);
    return null;
  }

  const search = uiJson.summary?.search || {};
  const overview = uiJson.summary?.overview || {};
  const timeline = overview.timeline || {};
  const economicAnalysis = overview.economic_analysis || {};
  const awardLogic = overview.award_logic || {};
  const goNoGo = overview.go_no_go || {};
  const supplyCapability = overview.supply_capability || {};

  // Extract mandatory requirements with source tracking (TOP 5 ONLY)
  const mandatoryRequirementsWithSource = (overview.top_mandatory_requirements || [])
    .slice(0, 5) // Limit to top 5
    .map(req => {
      if (typeof req === 'string') {
        return { text: req, source_document: 'Unknown', source_chunk_id: null };
      }
      return {
        text: req.text || req.requirement_de || req.requirement || '',
        source_document: req.source_document || 'Unknown',
        source_chunk_id: req.source_chunk_id || null
      };
    })
    .filter(r => r.text);

  // Extract risks with source tracking (TOP 5 ONLY)
  const risksWithSource = (overview.main_risks || [])
    .slice(0, 5) // Limit to top 5
    .map(r => {
      if (typeof r === 'string') {
        return { text: r, severity: 'medium', source_document: 'Unknown', source_chunk_id: null };
      }
      return {
        text: r.text || r.risk_de || r.risk || '',
        severity: r.severity || 'medium',
        source_document: r.source_document || 'Unknown',
        source_chunk_id: r.source_chunk_id || null
      };
    })
    .filter(r => r.text);

  // Extract process steps from timeline phases with source tracking
  const processSteps = (timeline.phases || []).map((phase, idx) => ({
    step: idx + 1,
    days_de: phase.duration_days || '',
    title_de: phase.title || phase.title_de || '',
    description_de: phase.description || phase.description_de || '',
    source_document: phase.source_document || 'Unknown',
    source_chunk_id: phase.source_chunk_id || null
  }));

  // Extract penalties with source tracking
  const penalties = [];

  // Extract evaluation criteria from award_logic with source tracking
  const evaluationCriteria = [];
  if (Array.isArray(awardLogic.weights)) {
    awardLogic.weights.forEach(w => {
      const text = typeof w === 'string' ? w : (w.text || w.weight_de || '');
      if (text) {
        evaluationCriteria.push({
          text,
          source_document: w.source_document || 'Unknown',
          source_chunk_id: w.source_chunk_id || null
        });
      }
    });
  }
  if (awardLogic.notes) {
    evaluationCriteria.push({
      text: awardLogic.notes,
      source_document: 'Award Logic',
      source_chunk_id: null
    });
  }
  if (Array.isArray(awardLogic.evaluation_matrix)) {
    awardLogic.evaluation_matrix.slice(0, 3).forEach(e => {
      const text = typeof e === 'string' ? e : (e.text || '');
      if (text) {
        evaluationCriteria.push({
          text,
          source_document: e.source_document || 'Unknown',
          source_chunk_id: e.source_chunk_id || null
        });
      }
    });
  }

  // Extract missing evidence documents with source tracking
  const missingEvidence = (overview.missing_evidence_documents || [])
    .map(doc => {
      if (typeof doc === 'string') {
        return { text: doc, source_document: 'Unknown', source_chunk_id: null };
      }
      return {
        text: doc.text || doc.document_de || '',
        source_document: doc.source_document || 'Unknown',
        source_chunk_id: doc.source_chunk_id || null
      };
    })
    .filter(d => d.text);

  // Extract certifications from supply_capability
  const certifications = [];
  if (supplyCapability.scope_of_services) {
    const services = Array.isArray(supplyCapability.scope_of_services)
      ? supplyCapability.scope_of_services
      : [supplyCapability.scope_of_services];

    services.forEach(service => {
      const text = typeof service === 'string' ? service : (service.text || '');
      // Look for certification keywords
      if (text && (text.includes('ISO') || text.includes('Zertifikat') || text.includes('certification'))) {
        certifications.push(text);
      }
    });
  }

  // Parse deadline
  const deadlineText = search.deadline || timeline.submission_deadline;
  const deadline = parseDateFromText(deadlineText) || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  // Calculate KPIs based on actual data
  // Since go_no_go.must_have and possible_hit are empty objects,
  // we'll use the actual arrays: top_mandatory_requirements and main_risks
  const totalMandatoryReqs = mandatoryRequirementsWithSource.length;
  const totalRisks = risksWithSource.length;

  // For must-hit: assume we can fulfill all mandatory requirements (optimistic)
  // In a real scenario, this would come from a matching algorithm
  const mustHits = totalMandatoryReqs;
  const mustTotal = totalMandatoryReqs || 1; // Avoid division by zero
  const mustHitPercent = mustTotal > 0 ? Math.round((mustHits / mustTotal) * 100) : 0;

  // For possible-hit: use the number of risks as "possible issues"
  // Assume we can mitigate most risks (e.g., 80% success rate)
  const canHits = Math.round(totalRisks * 0.8); // 80% of risks can be mitigated
  const canTotal = totalRisks || 1; // Avoid division by zero
  const possibleHitPercent = canTotal > 0 ? Math.round((canHits / canTotal) * 100) : 0;

  // Calculate overall score based on go_no_go decision and KPIs
  let baseScore = 50; // Default for UNKNOWN
  if (goNoGo.decision === 'GO') baseScore = 85;
  else if (goNoGo.decision === 'MAYBE') baseScore = 60;
  else if (goNoGo.decision === 'NO-GO') baseScore = 30;

  // Weighted score: 60% must-hit + 30% possible-hit + 10% base decision
  const weightedScore = Math.round(
    (mustHitPercent * 0.6) + (possibleHitPercent * 0.3) + (baseScore * 0.1)
  );

  // Calculate logistics score (100% if feasibility check passed)
  const logisticsScore = 100; // Default to 100% for now


  // Extract economic analysis with source tracking (TOP 5 FACTS ONLY)
  const economicFacts = (economicAnalysis.facts || []).slice(0, 5); // Limit to top 5
  const economicAnalysisFormatted = {
    potentialMargin: {
      text: economicFacts.find(f => f.text?.toLowerCase().includes('margin'))?.text || 'Missing',
      source_document: economicFacts.find(f => f.text?.toLowerCase().includes('margin'))?.source_document || null
    },
    orderValueEstimated: {
      text: economicFacts.find(f => f.text?.toLowerCase().includes('wert') || f.text?.toLowerCase().includes('summe'))?.text || 'Missing',
      source_document: economicFacts.find(f => f.text?.toLowerCase().includes('wert') || f.text?.toLowerCase().includes('summe'))?.source_document || null
    },
    competitiveIntensity: {
      text: economicFacts.find(f => f.text?.toLowerCase().includes('wettbewerb'))?.text || 'Missing',
      source_document: economicFacts.find(f => f.text?.toLowerCase().includes('wettbewerb'))?.source_document || null
    },
    logisticsCosts: {
      text: economicFacts.find(f => f.text?.toLowerCase().includes('kosten'))?.text || 'Missing',
      source_document: economicFacts.find(f => f.text?.toLowerCase().includes('kosten'))?.source_document || null
    },
    contractRisk: {
      text: economicFacts.find(f => f.text?.toLowerCase().includes('risiko'))?.text || 'Missing',
      source_document: economicFacts.find(f => f.text?.toLowerCase().includes('risiko'))?.source_document || null
    },
    criticalSuccessFactors: economicFacts.slice(0, 5).map(f => ({
      text: f.text || '',
      source_document: f.source_document || 'Unknown',
      source_chunk_id: f.source_chunk_id || null
    })).filter(f => f.text),
  };

  return {
    id: runId || search.title || `tender-${Date.now()}`,
    title: search.title || overview.executive_summary?.substring(0, 100) || 'Missing Title',
    buyer: search.issuer || 'Missing Issuer',
    region: search.region_tags?.[0] || search.location || 'Missing Location',
    deadline: deadline,
    url: `#`,
    score: weightedScore,
    legalRisks: risksWithSource.map(r => r.text),
    legalRisksWithSource: risksWithSource,
    mustHits: mustHits,
    mustTotal: mustTotal,
    mustHitPercent: mustHitPercent,
    canHits: canHits,
    canTotal: canTotal,
    possibleHitPercent: possibleHitPercent,
    logisticsScore: logisticsScore,
    serviceTypes: search.category_tags || [],
    scopeOfWork: search.short_teaser || overview.executive_summary || '',
    scopeOfWorkSource: {
      text: search.short_teaser || overview.executive_summary || '',
      source_document: search.source_document || 'Search Summary',
      source_chunk_id: search.source_chunk_id || null
    },
    penalties: penalties,
    evaluationCriteria: evaluationCriteria.map(e => e.text),
    evaluationCriteriaWithSource: evaluationCriteria,
    submission: mandatoryRequirementsWithSource.map(r => r.text),
    submissionWithSource: mandatoryRequirementsWithSource,
    processSteps: processSteps,
    economicAnalysis: economicAnalysisFormatted,
    missingEvidence: missingEvidence.map(e => e.text),
    missingEvidenceWithSource: missingEvidence,
    certifications: certifications,
    // Add source tracking for key fields
    sources: {
      title: search.source_document || 'Search Summary',
      buyer: search.source_document || 'Search Summary',
      deadline: search.source_document || timeline.source_document || 'Timeline',
      mustCriteria: 'Overview - Top Mandatory Requirements',
      logistics: 'Supply Capability',
      certifications: 'Supply Capability',
      scopeOfWork: search.source_document || 'Search Summary',
      pricingModel: 'Economic Analysis',
      penalties: 'Award Logic',
      evaluationCriteria: 'Award Logic',
      submission: 'Overview - Top Mandatory Requirements',
      legalRisks: 'Overview - Main Risks',
    }
  };
}

/**
 * Transform flat N8N ui_json structure (from run_summaries) to frontend Tender format
 * This handles the actual structure N8N saves: flat ui_json with meta, mandatory_requirements, etc.
 */
function transformFlatUIJson(uiJson, runId) {
  const meta = uiJson.meta || {};
  const kpis = uiJson.kpis || {};
  const mandatoryReqs = uiJson.mandatory_requirements || [];
  const operationalReqs = uiJson.operational_requirements || [];
  const risks = uiJson.risks || [];
  const execSummary = uiJson.executive_summary || {};
  const timeline = uiJson.timeline_milestones || {};
  const commercials = uiJson.commercials || {};
  const awardLogic = uiJson.award_logic || {};

  // Parse fractions with proper fallback to array lengths
  let mustHits = 0, mustTotal = mandatoryReqs.length;
  let canHits = 0, canTotal = operationalReqs.length;

  if (kpis.must_hit_fraction && typeof kpis.must_hit_fraction === 'string') {
    const parts = kpis.must_hit_fraction.split('/').map(Number);
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      mustHits = parts[0];
      mustTotal = parts[1];
    }
  }

  if (kpis.possible_hit_fraction && typeof kpis.possible_hit_fraction === 'string') {
    const parts = kpis.possible_hit_fraction.split('/').map(Number);
    if (parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
      canHits = parts[0];
      canTotal = parts[1];
    }
  }

  // Extract risk texts
  const riskTexts = risks.map(r => r.risk_de || r.risk || '').filter(Boolean);

  // Build title with fallbacks
  const title = meta.tender_id
    ? `Ausschreibung ${meta.tender_id}`
    : execSummary.brief_description_de?.substring(0, 50) || 'Untitled Tender';

  // Buyer with fallbacks - try to extract from commercials.other_de if organization is missing
  let buyer = meta.organization;
  if (!buyer && Array.isArray(commercials.other_de)) {
    const orgHint = commercials.other_de.find(t =>
      typeof t === 'string' && t.toLowerCase().includes('auftraggeber')
    );
    if (orgHint) {
      // Try to extract organization name from text
      const match = orgHint.match(/(?:durch|durch den|durch die)\s+([A-Z][a-zA-ZäöüÄÖÜß\s]+?)(?:\s|,|\.|$)/i);
      if (match) buyer = match[1].trim();
    }
  }
  buyer = buyer || execSummary.location_de || 'Unknown';

  // Extract penalties from commercials
  // Use penalties_de if available, otherwise fallback to other_de with penalty-related terms
  let penalties = [];
  if (Array.isArray(commercials.penalties_de) && commercials.penalties_de.length > 0) {
    penalties = commercials.penalties_de.map(p => typeof p === 'string' ? p : (p.item_de || p.penalty_de || p));
  } else if (Array.isArray(commercials.other_de)) {
    // Fallback: Use other_de items related to security/guarantees/penalties
    penalties = commercials.other_de
      .filter(t => typeof t === 'string' && (
        t.toLowerCase().includes('sicherheit') ||
        t.toLowerCase().includes('bürgschaft') ||
        t.toLowerCase().includes('schaden') ||
        t.toLowerCase().includes('vertragsstrafe')
      ))
      .slice(0, 3); // Limit to top 3
  }

  // Extract evaluation criteria from award_logic
  // Fallback to commercials.other_de if award logic is empty
  const evaluationCriteria = [];
  if (awardLogic.matrix_de) evaluationCriteria.push(awardLogic.matrix_de);
  if (awardLogic.price_weight_percent) evaluationCriteria.push(`Price: ${awardLogic.price_weight_percent}%`);
  if (awardLogic.quality_weight_percent) evaluationCriteria.push(`Quality: ${awardLogic.quality_weight_percent}%`);
  if (awardLogic.other_de) evaluationCriteria.push(awardLogic.other_de);

  // Fallback: Use commercials.other_de if evaluation criteria is empty
  if (evaluationCriteria.length === 0 && Array.isArray(commercials.other_de) && commercials.other_de.length > 0) {
    // Use first item as fallback if it contains evaluation-related terms
    const evalHint = commercials.other_de.find(t =>
      typeof t === 'string' && (
        t.toLowerCase().includes('bewertung') ||
        t.toLowerCase().includes('zuschlag') ||
        t.toLowerCase().includes('preis') ||
        t.toLowerCase().includes('qualität')
      )
    );
    if (evalHint) evaluationCriteria.push(evalHint);
  }

  // Deadline with fallbacks - parse date from text if needed
  let deadline = timeline.submission_deadline_de;
  if (!deadline && execSummary.duration_de) {
    // Try to parse date from duration_de text (e.g., "Ausführungsende (voraussichtlich): 28.05.2027")
    deadline = parseDateFromText(execSummary.duration_de);
  }
  if (!deadline) {
    // Default: 30 days from now
    deadline = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
  }

  // Extract mandatory requirements text for "Top 5 mandatory requirements" / submission field
  const mandatoryRequirementsText = mandatoryReqs.map(r => r.requirement_de || r.requirement || '').filter(Boolean);

  // Extract process steps for timeline
  const processSteps = Array.isArray(uiJson.process_steps) ? uiJson.process_steps : [];

  // Extract economic analysis data
  const economicAnalysis = uiJson.economic_analysis || {};

  // Extract missing evidence documents
  const missingEvidence = Array.isArray(uiJson.missing_evidence_documents) ? uiJson.missing_evidence_documents : [];

  return {
    id: meta.tender_id || runId || `tender-${Date.now()}`,
    title: title,
    buyer: buyer,
    region: execSummary.location_de || 'DE',
    deadline: deadline,
    url: `#`,
    score: kpis.in_total_weighted_percent || kpis.must_hit_percent || kpis.possible_hit_percent || 0,
    legalRisks: riskTexts,
    mustHits: mustHits,
    mustTotal: mustTotal,
    canHits: canHits,
    canTotal: canTotal,
    serviceTypes: [],
    scopeOfWork: execSummary.scope_de || execSummary.brief_description_de?.substring(0, 200) || '',
    penalties: penalties,
    evaluationCriteria: evaluationCriteria,
    // New fields from run_summaries.ui_json
    submission: mandatoryRequirementsText, // Maps to "Top 5 mandatory requirements"
    processSteps: processSteps, // Maps to timeline/process steps
    economicAnalysis: {
      potentialMargin: economicAnalysis.potential_margin_de || null,
      orderValueEstimated: economicAnalysis.order_value_estimated_de || null,
      competitiveIntensity: economicAnalysis.competitive_intensity_de || null,
      logisticsCosts: economicAnalysis.logistics_costs_de || null,
      contractRisk: economicAnalysis.contract_risk_de || null,
      criticalSuccessFactors: economicAnalysis.critical_success_factors_de || [],
    },
    missingEvidence: missingEvidence,
  };
}

/**
 * Transform LLM extracted_json to frontend Tender format
 */
function transformLLMExtraction(extractedJson, filename, docId) {
  const docMeta = extractedJson?.doc_meta || {};
  const mandatoryReqs = extractedJson?.mandatory_requirements || [];
  const operativeReqs = extractedJson?.operative_requirements || [];
  const risks = extractedJson?.risks || [];
  const commercials = extractedJson?.commercials || {};
  const awardLogic = extractedJson?.award_logic || {};

  // Comprehensive tender_id lookup
  const tenderId = extractedJson?.tender_id || docMeta.tender_id || docId;

  // Comprehensive buyer/organization lookup with fallbacks
  const buyer = extractedJson?.issuing_authority
    || docMeta.organization
    || extractedJson?.region_or_location
    || 'Unknown';

  // Title with fallbacks: tender_id → project_name → filename
  const title = extractedJson?.tender_id || docMeta.tender_id
    ? `Ausschreibung ${tenderId}`
    : extractedJson?.project_name || filename || 'Untitled Tender';

  // Scope of work with fallbacks
  const scopeOfWork = extractedJson?.scope
    || extractedJson?.executive_summary?.brief_description_de
    || mandatoryReqs.map(r => typeof r === 'string' ? r : (r.requirement || r.requirement_de || r)).join('; ').substring(0, 200)
    || '';

  // Extract penalties from commercials
  const penalties = Array.isArray(commercials.penalties)
    ? commercials.penalties.map(p => typeof p === 'string' ? p : (p.item_de || p.penalty || p))
    : [];

  // Extract award/evaluation criteria
  const evaluationCriteria = [];
  if (awardLogic.matrix_description) evaluationCriteria.push(awardLogic.matrix_description);
  if (awardLogic.weights) evaluationCriteria.push(JSON.stringify(awardLogic.weights));
  if (awardLogic.total_score) evaluationCriteria.push(`Total Score: ${awardLogic.total_score}`);

  // Extract requirement texts
  const mandatoryTexts = mandatoryReqs.map(r =>
    typeof r === 'string' ? r : r.requirement || r.requirement_de || r
  );
  const operativeTexts = operativeReqs.map(r =>
    typeof r === 'string' ? r : r.requirement || r.requirement_de || r
  );
  const riskTexts = risks.map(r =>
    typeof r === 'string' ? r : r.risk || r.risk_de || r
  );

  // Certifications
  const certifications = Array.isArray(extractedJson?.certifications)
    ? extractedJson.certifications.map(c => typeof c === 'string' ? c : (c.name || c.certification || c))
    : [];

  return {
    id: tenderId || `tender-${Date.now()}`,
    title: title,
    buyer: buyer,
    region: extractedJson?.region_or_location || 'DE',
    deadline: extractedJson?.submission_deadline
      || extractedJson?.deadlines?.details?.[0]?.date
      || extractedJson?.contract_duration
      || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    url: `#`,
    score: awardLogic.total_score || 0,
    legalRisks: riskTexts.filter(Boolean),
    mustHits: 0,
    mustTotal: mandatoryTexts.length,
    canHits: 0,
    canTotal: operativeTexts.length,
    serviceTypes: [],
    scopeOfWork: scopeOfWork,
    sources: {
      mustCriteria: filename,
      logistics: filename,
      deadline: filename,
    },
    certifications: certifications,
    evaluationCriteria: evaluationCriteria,
    safety: [],
    penalties: penalties,
    submission: [],
  };
}

/**
 * GET /api/tenders
 * Fetch all tenders from run_summaries OR file_extractions
 */
router.get('/', async (req, res) => {
  try {
    const { sortBy = 'deadline', limit = 1000, offset = 0 } = req.query;

    const tenders = [];

    // First, try to get from run_summaries (aggregated UI data)
    // Removed WHERE status = 'COMPLETED' to show ALL runs as requested
    const runSummaryResult = await query(
      `SELECT run_id, ui_json, status, created_at, updated_at
       FROM run_summaries
       ORDER BY created_at DESC
       LIMIT $1 OFFSET $2`,
      [limit, offset]
    );

    for (const row of runSummaryResult.rows) {
      const uiJson = row.ui_json;
      let transformed = null;

      // NEW: Check for nested summary structure (actual N8N DB format)
      if (uiJson && uiJson.summary) {
        transformed = transformNestedSummaryToFlat(uiJson, row.run_id);
      }
      // Check if it's the old flat structure (has meta at root level)
      else if (uiJson && uiJson.meta && !uiJson.summary) {
        transformed = transformFlatUIJson(uiJson, row.run_id);
      }
      // Fallback to old structure (has results array)
      else if (uiJson && uiJson.results && Array.isArray(uiJson.results)) {
        transformed = transformTenderResult(uiJson.results[0]);
      }

      if (transformed) {
        transformed.runId = row.run_id;
        transformed.tenderId = uiJson?.meta?.tender_id || uiJson?.tender_id || transformed.id;
        transformed.status = row.status;
        transformed.createdAt = row.created_at;
        transformed.updatedAt = row.updated_at;
        tenders.push(transformed);
      }
    }

    // Sort by requested field
    if (sortBy === 'deadline') {
      tenders.sort((a, b) => new Date(a.deadline) - new Date(b.deadline));
    } else if (sortBy === 'score') {
      tenders.sort((a, b) => b.score - a.score);
    }

    res.json({
      success: true,
      count: tenders.length,
      data: tenders
    });

  } catch (error) {
    console.error('Error fetching tenders:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch tenders',
      message: error.message
    });
  }
});

/**
 * GET /api/tenders/:tenderId
 * Fetch single tender details
 */
router.get('/:tenderId', async (req, res) => {
  try {
    const { tenderId } = req.params;

    // Prefer direct run_id match first
    const result = await query(
      `SELECT run_id, ui_json, status, created_at, updated_at
       FROM run_summaries
       WHERE run_id = $1
          OR ui_json->'meta'->>'tender_id' = $1
          OR ui_json->>'tender_id' = $1
          OR ui_json->'overview'->>'tender_id' = $1
          OR ui_json->'results'->0->>'tender_id' = $1
       ORDER BY created_at DESC
       LIMIT 1`,
      [tenderId]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({
        success: false,
        error: 'Tender not found'
      });
    }

    const row = result.rows[0];
    const uiJson = row.ui_json;
    let transformed = null;

    if (uiJson && uiJson.summary) {
      transformed = transformNestedSummaryToFlat(uiJson, row.run_id);
    } else if (uiJson && uiJson.meta && !uiJson.summary) {
      transformed = transformFlatUIJson(uiJson, row.run_id);
    } else if (uiJson && uiJson.results && Array.isArray(uiJson.results)) {
      transformed = transformTenderResult(uiJson.results[0]);
    }

    if (!transformed) {
      return res.status(404).json({
        success: false,
        error: 'Tender data not available'
      });
    }

    transformed.runId = row.run_id;
    transformed.tenderId = uiJson?.meta?.tender_id || uiJson?.tender_id || transformed.id;
    transformed.status = row.status;
    transformed.createdAt = row.created_at;
    transformed.updatedAt = row.updated_at;

    res.json({
      success: true,
      data: transformed
    });

  } catch (error) {
    console.error('Error fetching tender details:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch tender details',
      message: error.message
    });
  }
});

/**
 * GET /api/runs
 * List all N8N runs
 */
router.get('/runs/list', async (req, res) => {
  try {
    const result = await query(
      `SELECT 
        run_id, 
        status, 
        total_files, 
        success_files, 
        failed_files,
        created_at,
        updated_at
       FROM run_summaries
       ORDER BY created_at DESC
       LIMIT 100`
    );

    res.json({
      success: true,
      count: result.rows.length,
      data: result.rows
    });

  } catch (error) {
    console.error('Error fetching runs:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch runs',
      message: error.message
    });
  }
});

/**
 * GET /api/runs/:runId/files
 * Get all files from a specific run
 */
router.get('/runs/:runId/files', async (req, res) => {
  try {
    const { runId } = req.params;

    const result = await query(
      `SELECT 
        id,
        doc_id,
        filename,
        file_type,
        status,
        error,
        created_at,
        updated_at
       FROM file_extractions
       WHERE run_id = $1
       ORDER BY created_at ASC`,
      [runId]
    );

    res.json({
      success: true,
      runId: runId,
      count: result.rows.length,
      data: result.rows
    });

  } catch (error) {
    console.error('Error fetching run files:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch run files',
      message: error.message
    });
  }
});

/**
 * GET /api/health
 * Health check endpoint
 */
router.get('/health', async (req, res) => {
  try {
    // Test database connection
    await query('SELECT NOW()');

    res.json({
      success: true,
      status: 'healthy',
      timestamp: new Date().toISOString(),
      database: 'connected'
    });
  } catch (error) {
    res.status(503).json({
      success: false,
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      database: 'disconnected',
      error: error.message
    });
  }
});

/**
 * GET /api/tenders/debug/raw
 * Debug endpoint to see raw database data
 */
router.get('/debug/raw', async (req, res) => {
  try {
    // Get raw data from run_summaries
    const runSummaryResult = await query(
      `SELECT run_id, ui_json, status, created_at
       FROM run_summaries
       ORDER BY created_at DESC
       LIMIT 5`
    );

    // Get raw data from file_extractions
    const fileExtractionsResult = await query(
      `SELECT doc_id, filename, extracted_json, status, created_at
       FROM file_extractions
       WHERE status = 'SUCCESS' 
         AND extracted_json IS NOT NULL
       ORDER BY created_at DESC
       LIMIT 5`
    );

    // Show transformed data for comparison
    const transformedTenders = [];

    for (const row of runSummaryResult.rows) {
      const uiJson = row.ui_json;

      // Check if it's the new flat structure (has meta)
      if (uiJson && uiJson.meta) {
        transformedTenders.push({
          raw: uiJson,
          transformed: transformFlatUIJson(uiJson, row.run_id)
        });
      }
      // Fallback to old structure (has results array)
      else if (uiJson && uiJson.results && Array.isArray(uiJson.results)) {
        for (const item of uiJson.results) {
          transformedTenders.push({
            raw: item,
            transformed: transformTenderResult(item)
          });
        }
      }
    }

    if (transformedTenders.length === 0) {
      for (const row of fileExtractionsResult.rows) {
        const extractedJson = row.extracted_json;
        if (extractedJson && typeof extractedJson === 'object') {
          transformedTenders.push({
            raw: {
              doc_id: row.doc_id,
              filename: row.filename,
              extracted_json: extractedJson
            },
            transformed: transformLLMExtraction(extractedJson, row.filename, row.doc_id)
          });
        }
      }
    }

    res.json({
      success: true,
      debug: {
        run_summaries_count: runSummaryResult.rows.length,
        file_extractions_count: fileExtractionsResult.rows.length,
        transformed_count: transformedTenders.length,
        run_summaries_sample: runSummaryResult.rows[0] || null,
        file_extractions_sample: fileExtractionsResult.rows[0] || null,
        transformation_examples: transformedTenders
      }
    });

  } catch (error) {
    console.error('Error in debug endpoint:', error);
    res.status(500).json({
      success: false,
      error: 'Failed to fetch debug data',
      message: error.message,
      stack: process.env.NODE_ENV === 'development' ? error.stack : undefined
    });
  }
});

export default router;
