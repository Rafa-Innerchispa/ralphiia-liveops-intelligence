(function () {
  const STORAGE_KEY = "liveops_lang";

  const STRINGS = {
    en: {
      pageTitle: "RalphiIA LiveOps Intelligence",
      heroSub:
        "Natural-language LiveOps on your real servers (read-only). Observed facts · web citations · local OSS reasoning · external review · human approval. Track: Multi-Agent Systems (You.com hackathon).",
      badgeTrack: "Track: Multi-Agent Systems",
      badgeDry: "Dry-run · no production changes",
      badgeYoucom: "You.com …",
      badgeParasail: "Parasail …",
      runBtn: "Run live analysis",
      ctaLiveStatus: "1 · Check Live Status",
      ctaInvestigate: "2 · Investigate with Live Sources",
      ctaGitHub: "3 · Create GitHub Incident",
      ctaRenderWorkflow: "Run as Render Workflow",
      ctaRenderWorkflowBadge: "Orchestrated by Render Workflows",
      ctaHelp:
        "Demo order: (1) live status only — saves You.com credits. (2) web research + Parasail with citations. (3) opens after a run finishes — GitHub incident preview (needs ONE_SECRET or GITHUB_TOKEN on server).",
      ctaGitHubDisabled: "Complete step 1 or 2 first",
      promptLiveStatus: "What is currently unhealthy in my infrastructure? Use live read-only evidence only.",
      promptInvestigate:
        "Evaluate my servers and give possible solutions with web-backed recommendations and citations for the problem found. Do not change production.",
      incidentModalTitle: "Create GitHub incident (preview)",
      incidentModalHint: "Edit title/body, then approve. Created via One MCP when ONE_SECRET is set, else GitHub API.",
      issueTitleLabel: "Title",
      issueBodyLabel: "Body (markdown)",
      issueCreateBtn: "Approve & create issue",
      issueCancelBtn: "Cancel",
      issueCreated: "Issue created:",
      errIncidentPreview: "Could not build preview:",
      loadIncidentBtn: "Load suggested incident",
      probeBtn: "Quick You.com probe",
      chatLabel: "Ask anything about the live infrastructure…",
      chatHint: "Enter to send · Shift+Enter for new line",
      chip1: "Check current health",
      chip2: "Investigate an incident",
      chip3: "What should I do next without changing production?",
      chip4: "Research this error deeper",
      liveNodesTitle: "Live nodes snapshot",
      dataSourcesTitle: "Used in this run",
      hybridStackTitle: "Hybrid intelligence stack",
      modelsUsed: "Models used",
      modelsAvail: "Available local models (display)",
      nodesUnavailable: "Nodes snapshot unavailable",
      metricLocalLat: "Local latency",
      pipeLocal: "Ollama OSS",
      pipeHuman: "Final control",
      jsonSummary: "Technical evidence (JSON)",
      incidentTitle: "Active incident (real RalfIA case)",
      scenarioText:
        "Evolution API on AMD node (.5): systemd=active but health=down — WhatsApp line blocked; operator agreed not to recover until return from travel.",
      idLabel: "ID:",
      corrLabel: "Correlation:",
      storyProblemTitle: "Problem",
      storyStepsTitle: "Data chain (4 agents)",
      storyProblem:
        "In production, the AMD node (.5) runs Evolution API with systemd active but health down due to a blocked WhatsApp line. A single LLM would say “restart the service” without citations. Here each agent has a role and data flows: observation → cited web (You.com) → security → verdict.",
      pipeObserver: "RalfIA read-only",
      pipeResearch: "You.com MCP",
      pipeSecurity: "Parasail",
      pipeArbitrator: "Recommendation",
      feedTitle: "Live data flow",
      storyRefTitle: "Architecture reference (static — not your live answer)",
      humanCheckpointHint:
        "Security “approved” in JSON means the reviewer agent allowed a dry-run recommendation — it is NOT you. Click Approve / Reject below to record your human checkpoint (still zero production changes).",
      naturalAnswerLabel: "Natural-language answer",
      technicalTraceLabel: "API trace (this run)",
      traceEmpty: "Send a question — each line is an outbound HTTP/MCP call or an explicit skip.",
      feedEmpty:
        "Send a question or run live analysis. You will see each request/response here (Search → Contents → Research may take ~30 s).",
      verdictTitle: "Final recommendation",
      operatorSummary: "Operator summary",
      jsonSummary: "Structured JSON (judges)",
      approveBtn: "Approve (checkpoint)",
      rejectBtn: "Reject",
      deeperBtn: "Research deeper",
      facts: "Observed facts",
      hypotheses: "Model hypotheses",
      cites: "Citations",
      noCites: "No citations in this step",
      metricCites: "Citations",
      metricTime: "Time",
      metricConf: "Confidence",
      metricRisk: "Risk",
      stateRunning: "Running…",
      stateDone: "Completed",
      providersTitle: "Models in this run",
      errBackend: "Could not reach backend. Is uvicorn on :8788?",
      errStream:
        "Stream interrupted (timeout or network). Retry — during You.com Research the bar keeps moving with data_flow events.",
      errRunFirst: "Run analysis first",
      flowStartTitle: "Pipeline start",
      flowStartExplain: "Track {track} · incident {incident}",
      lastRun: "Last run:",
      youcomMode: "You.com mode:",
      probeOk: "You.com probe OK · mode",
      probeFail: "Probe failed:",
      agentObserver: "Observer",
      agentLocal: "Local Analyst · Ollama",
      agentResearch: "You.com Research",
      agentSecurity: "Security · Parasail",
      agentArbitrator: "Arbitrator",
      opseraTitle: "Built & reviewed with (development-time)",
    },
    es: {
      pageTitle: "RalphiIA LiveOps Intelligence",
      heroSub:
        "Qué hace: simula cómo RalfIA respondería a un incidente real — cada paso es una llamada de datos real (HTTP RalfIA, MCP You.com, LLM Parasail), no texto estático. Track hackathon: Multi-Agent Systems.",
      badgeTrack: "Track: Multi-Agent Systems",
      badgeDry: "Dry-run · sin cambios en producción",
      badgeYoucom: "You.com …",
      badgeParasail: "Parasail …",
      runBtn: "Ejecutar análisis en vivo",
      ctaLiveStatus: "1 · Comprobar estado live",
      ctaInvestigate: "2 · Investigar con fuentes live",
      ctaGitHub: "3 · Crear incidente GitHub",
      ctaRenderWorkflow: "Ejecutar como Render Workflow",
      ctaRenderWorkflowBadge: "Orquestado por Render Workflows",
      ctaHelp:
        "Orden demo: (1) solo estado live — ahorra créditos You.com. (2) investigación web + Parasail con citas. (3) se habilita al terminar 1 o 2 — preview de issue GitHub (requiere ONE_SECRET o GITHUB_TOKEN en servidor).",
      ctaGitHubDisabled: "Completa el paso 1 o 2 primero",
      promptLiveStatus: "¿Qué está unhealthy en mi infraestructura? Solo evidencia read-only.",
      promptInvestigate:
        "Evalúa mis servidores y da soluciones con citas web. Sin cambiar producción.",
      incidentModalTitle: "Crear incidente GitHub (vista previa)",
      incidentModalHint: "Edita y aprueba. One MCP si ONE_SECRET está configurado.",
      issueTitleLabel: "Título",
      issueBodyLabel: "Cuerpo (markdown)",
      issueCreateBtn: "Aprobar y crear issue",
      issueCancelBtn: "Cancelar",
      issueCreated: "Issue creado:",
      errIncidentPreview: "No se pudo generar preview:",
      loadIncidentBtn: "Cargar incidente sugerido",
      probeBtn: "Probar You.com (rápido)",
      chatLabel: "Pregunta lo que quieras sobre la infraestructura en vivo…",
      chatHint: "Enter envía · Shift+Enter nueva línea",
      chip1: "Comprobar salud actual",
      chip2: "Investigar un incidente",
      chip3: "¿Qué harías sin cambiar producción?",
      chip4: "Investigar más a fondo este error",
      liveNodesTitle: "Snapshot de nodos",
      dataSourcesTitle: "Usado en esta ejecución",
      hybridStackTitle: "Stack híbrido",
      modelsUsed: "Modelos usados",
      modelsAvail: "Modelos locales disponibles (solo display)",
      nodesUnavailable: "Snapshot de nodos no disponible",
      metricLocalLat: "Latencia local",
      pipeLocal: "Ollama OSS",
      pipeHuman: "Control final",
      jsonSummary: "Evidencia técnica (JSON)",
      incidentTitle: "Incidente activo (caso real RalfIA)",
      scenarioText:
        "Evolution API en nodo AMD (.5): systemd=active pero health=down — línea WhatsApp bloqueada; operador de acuerdo en no recuperar hasta regreso del viaje.",
      idLabel: "ID:",
      corrLabel: "Correlación:",
      storyProblemTitle: "Problema",
      storyStepsTitle: "Cadena de datos (4 agentes)",
      storyProblem:
        "En producción, el nodo AMD (.5) tiene Evolution API con systemd activo pero health down por línea WhatsApp bloqueada. Un solo LLM diría «reinicia el servicio» sin citas. Aquí cada agente tiene un rol: observación → web citada (You.com) → seguridad → veredicto.",
      pipeObserver: "RalfIA read-only",
      pipeResearch: "You.com MCP",
      pipeSecurity: "Parasail",
      pipeArbitrator: "Recomendación",
      feedTitle: "Flujo de datos en vivo",
      storyRefTitle: "Referencia de arquitectura (estática — no es tu respuesta en vivo)",
      humanCheckpointHint:
        "“Approved” en JSON = agente Security, no tú. Pulsa Approve / Reject abajo para tu checkpoint humano (sin cambios en producción).",
      naturalAnswerLabel: "Respuesta en lenguaje natural",
      technicalTraceLabel: "Traza API (esta ejecución)",
      traceEmpty: "Envía una pregunta — cada línea es una llamada HTTP/MCP real o un skip explícito.",
      feedEmpty:
        "Envía una pregunta o ejecuta análisis en vivo. Verás cada request/response aquí (Search → Contents → Research puede tardar ~30 s).",
      verdictTitle: "Recomendación final",
      operatorSummary: "Resumen para operador",
      jsonSummary: "JSON estructurado (judges)",
      approveBtn: "Approve (checkpoint)",
      rejectBtn: "Reject",
      deeperBtn: "Research deeper",
      facts: "Hechos observados",
      hypotheses: "Hipótesis del modelo",
      cites: "Citas",
      noCites: "Sin citas en este paso",
      metricCites: "Citas",
      metricTime: "Tiempo",
      metricConf: "Confianza",
      metricRisk: "Riesgo",
      stateRunning: "En curso…",
      stateDone: "Completado",
      providersTitle: "Modelos en esta ejecución",
      errBackend: "No se pudo contactar el backend. ¿Está uvicorn en :8788?",
      errStream:
        "Stream interrumpido (timeout o red). Reintenta — durante You.com Research la barra sigue con eventos data_flow.",
      errRunFirst: "Ejecuta el análisis primero",
      flowStartTitle: "Inicio de pipeline",
      flowStartExplain: "Track {track} · incidente {incident}",
      lastRun: "Último run:",
      youcomMode: "modo You.com:",
      probeOk: "You.com probe OK · modo",
      probeFail: "Probe falló:",
      agentObserver: "Observer",
      agentLocal: "Analista local · Ollama",
      agentResearch: "You.com Research",
      agentSecurity: "Security · Parasail",
      agentArbitrator: "Arbitrator",
      opseraTitle: "Construido y revisado con (tiempo de desarrollo)",
    },
  };

  function getLang() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "es" || stored === "en") return stored;
    return "en";
  }

  function setLang(lang) {
    localStorage.setItem(STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    applyI18n(lang);
    document.dispatchEvent(new CustomEvent("liveops:lang", { detail: lang }));
  }

  function t(key, lang) {
    const L = lang || getLang();
    return (STRINGS[L] && STRINGS[L][key]) || STRINGS.en[key] || key;
  }

  function applyI18n(lang) {
    const L = lang || getLang();
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key) el.textContent = t(key, L);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.getAttribute("data-i18n-placeholder");
      if (key) el.placeholder = t(key, L);
    });
    document.title = t("pageTitle", L);
    document.querySelectorAll("[data-lang-active]").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.langActive === L);
    });
  }

  window.LiveOpsI18n = { getLang, setLang, t, applyI18n, STRINGS };
})();
