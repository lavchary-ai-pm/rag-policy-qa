import { useState, useRef, useEffect } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001'

const ALL_SUGGESTIONS = [
  "What is the 401k employer match?",
  "How much parental leave do I get?",
  "Can I use ChatGPT for work?",
  "What happens to my salary if I move cities?",
  "What is the gift acceptance policy?",
  "How many days of PTO do new employees get?",
  "What is the minimum password length requirement?",
  "How long is the equity vesting schedule?",
  "What is the expense limit for team dinners?",
  "What MFA methods are acceptable?",
  "What medical plans are available?",
  "What professional development budget do I get?",
  "How many bereavement days do I get?",
  "What are the approved AI tools for work?",
  "What recognition programs does NorthStar offer?",
]

const EVAL_CASES = [
  {
    question: "I'm moving from NYC to Austin. What happens to my salary?",
    ground_truth: "Your salary will be adjusted from Zone 1 (100% modifier) to Zone 2 (90% modifier). The adjustment is effective the first of the month following your move. You must notify the People team at least 30 days before relocating. Austin must be in an approved remote work state.",
    difficulty: "conditional",
    description: "Answer depends on geographic zone mapping + notification rules. Tests conditional logic handling.",
  },
  {
    question: "What is NorthStar's policy on bringing pets to the office?",
    ground_truth: "The available policy documents do not contain information about a pet policy. The system should state it does not have enough information and direct the user to the People team.",
    difficulty: "refusal",
    description: "Topic not in any policy doc. System should refuse gracefully instead of hallucinating an answer.",
  },
  {
    question: "Can I use ChatGPT to analyze employee compensation data?",
    ground_truth: "No. Employee compensation data is classified as Confidential (Level 3), and Confidential data must never be input into any AI tool. Currently no AI tools are approved for Confidential data. Only Internal (Level 2) data can be used with approved AI tools like ChatGPT Enterprise.",
    difficulty: "compliance",
    description: "Cross-policy compliance: AI usage + data classification rules intersect. Wrong answer risks a data breach.",
  },
  {
    question: "A vendor sent me a $150 gift card during an RFP process. Can I keep it?",
    ground_truth: "No, you cannot keep it for two reasons: 1) During vendor selection processes (RFPs, contract renewals), no gifts of any value may be accepted from participating vendors, and 2) Gift cards are considered cash equivalents, which are never allowed regardless of value. You should decline or turn the gift over to the People team.",
    difficulty: "multi-rule",
    description: "Tests if RAG applies two independent rules together: RFP blackout period AND cash-equivalent prohibition.",
  },
  {
    question: "What happens to my stock options if I resign?",
    ground_truth: "If you voluntarily resign, vested stock options must be exercised within 90 days of termination. All unvested equity continues on the standard vesting schedule until your termination date, at which point unvested options are forfeited. RSUs that have vested are your property regardless of termination type.",
    difficulty: "cross-document",
    description: "Answer spans 3 equity rules across multiple docs. Tests cross-document retrieval and synthesis.",
  },
  {
    question: "What is the 401k employer match?",
    ground_truth: "NorthStar matches 100% of the first 4% of salary contributed, plus 50% of the next 2%. The maximum employer match is 5% of salary. Employees are immediately eligible to contribute, but employer matching begins after 6 months of employment.",
    difficulty: "precision",
    description: "Exact numbers matter for compliance. Tests retrieval and citation of specific financial thresholds.",
  },
  {
    question: "What MFA methods are acceptable?",
    ground_truth: "Acceptable MFA methods are hardware security key (preferred) and authenticator app (Google Authenticator, Authy). SMS-based MFA is not permitted.",
    difficulty: "precision",
    description: "Must state what is NOT allowed, not just what is. Tests explicit exclusion in security policy.",
  },
]

function EvalDashboard() {
  const [results, setResults] = useState({})
  const [runningId, setRunningId] = useState(null)

  const runEval = async (index) => {
    const evalCase = EVAL_CASES[index]
    setRunningId(index)
    try {
      const res = await fetch(`${API_URL}/api/eval-run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: evalCase.question,
          ground_truth: evalCase.ground_truth,
        }),
      })
      const data = await res.json()
      setResults(prev => ({ ...prev, [index]: data }))
    } catch {
      setResults(prev => ({
        ...prev,
        [index]: { answer: 'Error running evaluation.', sources: [], latency_ms: 0, ground_truth: evalCase.ground_truth },
      }))
    } finally {
      setRunningId(null)
    }
  }

  return (
    <div className="eval-dashboard">
      <div className="eval-intro">
        <h3>RAG Pipeline Evaluation</h3>
        <p>Run individual test cases to compare the RAG pipeline answer against the expected ground truth. Traces and eval scores are logged to Phoenix.</p>
        <a
          href="http://localhost:6006"
          target="_blank"
          rel="noopener noreferrer"
          className="phoenix-link-inline"
        >
          Open Phoenix Dashboard
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
        </a>
      </div>
      <div className="eval-cards">
        {EVAL_CASES.map((evalCase, i) => {
          const result = results[i]
          const isRunning = runningId === i
          const isDisabled = runningId !== null && runningId !== i

          return (
            <div key={i} className={`eval-card ${result ? 'has-result' : ''}`}>
              <div className="eval-card-header">
                <span className={`difficulty-badge ${evalCase.difficulty}`}>
                  {evalCase.difficulty}
                </span>
                <button
                  className="eval-run-btn"
                  onClick={() => runEval(i)}
                  disabled={isRunning || isDisabled}
                  aria-label={`Run evaluation for question ${i + 1}`}
                >
                  {isRunning ? 'Running...' : result ? 'Re-run' : 'Run'}
                </button>
              </div>
              <div className="eval-card-question">{evalCase.question}</div>
              <div className="eval-card-description">{evalCase.description}</div>

              {isRunning && (
                <div className="eval-card-loading">
                  <div className="loading-dots">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              )}

              {result && !isRunning && (
                <div className="eval-card-result">
                  {result.evals && (
                    <div className="eval-scores">
                      <div className={`eval-score-pill ${result.evals.qa_correctness?.label === 'correct' ? 'good' : 'poor'}`}>
                        QA: {result.evals.qa_correctness?.label}
                      </div>
                      <div className={`eval-score-pill ${result.evals.hallucination?.label === 'factual' ? 'good' : 'poor'}`}>
                        Faithfulness: {result.evals.hallucination?.label}
                      </div>
                      <div className={`eval-score-pill ${result.evals.completeness?.label === 'complete' ? 'good' : 'poor'}`}>
                        Completeness: {result.evals.completeness?.label}
                      </div>
                      {result.evals.qa_correctness?.explanation && (
                        <details className="eval-explanation">
                          <summary>QA reasoning</summary>
                          <p>{result.evals.qa_correctness.explanation}</p>
                        </details>
                      )}
                      {result.evals.hallucination?.explanation && (
                        <details className="eval-explanation">
                          <summary>Faithfulness reasoning</summary>
                          <p>{result.evals.hallucination.explanation}</p>
                        </details>
                      )}
                      {result.evals.completeness?.explanation && (
                        <details className="eval-explanation">
                          <summary>Completeness reasoning</summary>
                          <p>{result.evals.completeness.explanation}</p>
                        </details>
                      )}
                    </div>
                  )}
                  <div className="eval-comparison">
                    <div className="eval-col">
                      <div className="eval-col-label">RAG Answer</div>
                      <div className="eval-col-text">{result.answer}</div>
                      {result.sources && result.sources.length > 0 && (
                        <div className="eval-sources">
                          {result.sources.map((src, j) => (
                            <span key={j} className="source-badge">{src.doc_id}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="eval-col">
                      <div className="eval-col-label">Expected Answer</div>
                      <div className="eval-col-text">{result.ground_truth}</div>
                    </div>
                  </div>
                  {result.latency_ms > 0 && (
                    <div className="eval-card-meta">
                      Answered in {(result.latency_ms / 1000).toFixed(1)}s
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function App() {
  const [tab, setTab] = useState('chat')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const sendQuestion = async (question) => {
    const userMsg = { role: 'user', content: question }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const res = await fetch(`${API_URL}/api/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question }),
      })
      const data = await res.json()
      const assistantMsg = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources,
        latency_ms: data.latency_ms,
        span_id: data.span_id,
      }
      setMessages(prev => [...prev, assistantMsg])
    } catch {
      const errorMsg = {
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        sources: [],
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setLoading(false)
    }
  }

  const sendFeedback = async (messageIndex, rating) => {
    setMessages(prev => prev.map((msg, i) =>
      i === messageIndex ? { ...msg, feedback: rating } : msg
    ))
    const msg = messages[messageIndex]
    const question = messages[messageIndex - 1]?.content || ''
    try {
      await fetch(`${API_URL}/api/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          answer: msg.content,
          rating,
        }),
      })
    } catch {
      // Feedback is best-effort
    }
  }

  const runChatEval = async (messageIndex) => {
    const msg = messages[messageIndex]
    const question = messages[messageIndex - 1]?.content || ''

    setMessages(prev => prev.map((m, i) =>
      i === messageIndex ? { ...m, evalLoading: true } : m
    ))

    try {
      const res = await fetch(`${API_URL}/api/eval-chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          answer: msg.content,
          span_id: msg.span_id,
        }),
      })
      const data = await res.json()
      setMessages(prev => prev.map((m, i) =>
        i === messageIndex ? { ...m, evalLoading: false, evalResult: data.evals } : m
      ))
    } catch {
      setMessages(prev => prev.map((m, i) =>
        i === messageIndex ? { ...m, evalLoading: false, evalResult: { error: true } } : m
      ))
      window.open('http://localhost:6006', '_blank', 'noopener,noreferrer')
    }
  }

  const getFilteredSuggestions = () => {
    const asked = new Set(
      messages.filter(m => m.role === 'user').map(m => m.content)
    )
    return ALL_SUGGESTIONS.filter(q => !asked.has(q)).slice(0, 4)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    sendQuestion(input.trim())
  }

  return (
    <div className="app">
      <div className="header">
        <div className="header-top">
          <h1>NorthStar Policy Q&A</h1>
          <a
            href="http://localhost:6006"
            target="_blank"
            rel="noopener noreferrer"
            className="phoenix-btn"
            aria-label="View Traces & Evals on Phoenix"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            View Traces & Evals on Phoenix
          </a>
        </div>
        <div className="tabs">
          <button
            className={`tab ${tab === 'chat' ? 'active' : ''}`}
            onClick={() => setTab('chat')}
          >
            Chat
          </button>
          <button
            className={`tab ${tab === 'eval' ? 'active' : ''}`}
            onClick={() => setTab('eval')}
          >
            Eval Results
          </button>
        </div>
      </div>

      {tab === 'chat' ? (
        <>
          <div className="messages">
            {messages.length === 0 && !loading ? (
              <div className="welcome">
                <div className="welcome-icon">?</div>
                <h2>What would you like to know?</h2>
                <p>
                  I can answer questions about HR policies, benefits, leave,
                  compensation, security, and more.
                </p>
                <div className="suggestions">
                  {ALL_SUGGESTIONS.slice(0, 5).map((q, i) => (
                    <button
                      key={i}
                      className="suggestion-chip"
                      onClick={() => sendQuestion(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, i) => (
                  <div key={i} className={`message ${msg.role}`}>
                    <div className="message-label">
                      {msg.role === 'user' ? 'You' : 'Policy Assistant'}
                    </div>
                    <div className="message-bubble">{msg.content}</div>
                    {msg.role === 'assistant' && msg.content !== 'Sorry, something went wrong. Please try again.' && (
                      <div className="feedback-row">
                        {msg.feedback ? (
                          <span className="feedback-thanks">
                            Thanks for your feedback!
                          </span>
                        ) : (
                          <>
                            <span className="feedback-prompt">Was this helpful?</span>
                            <button
                              className="feedback-btn"
                              onClick={() => sendFeedback(i, 'positive')}
                              aria-label="Helpful"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/><path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                            </button>
                            <button
                              className="feedback-btn"
                              onClick={() => sendFeedback(i, 'negative')}
                              aria-label="Not helpful"
                            >
                              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/><path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                            </button>
                          </>
                        )}
                        {msg.span_id && !msg.evalResult && (
                          <button
                            className="eval-chat-btn"
                            onClick={() => runChatEval(i)}
                            disabled={msg.evalLoading}
                            aria-label="Run evaluation on this answer"
                          >
                            {msg.evalLoading ? 'Evaluating...' : 'Eval'}
                          </button>
                        )}
                      </div>
                    )}
                    {msg.evalResult && !msg.evalResult.error && (
                      <div className="chat-eval-result">
                        <div className="eval-scores">
                          <div className={`eval-score-pill ${msg.evalResult.hallucination?.label === 'factual' ? 'good' : 'poor'}`}>
                            Faithfulness: {msg.evalResult.hallucination?.label}
                          </div>
                          <div className={`eval-score-pill ${msg.evalResult.completeness?.label === 'complete' ? 'good' : 'poor'}`}>
                            Completeness: {msg.evalResult.completeness?.label}
                          </div>
                          {msg.evalResult.hallucination?.explanation && (
                            <details className="eval-explanation">
                              <summary>Faithfulness reasoning</summary>
                              <p>{msg.evalResult.hallucination.explanation}</p>
                            </details>
                          )}
                          {msg.evalResult.completeness?.explanation && (
                            <details className="eval-explanation">
                              <summary>Completeness reasoning</summary>
                              <p>{msg.evalResult.completeness.explanation}</p>
                            </details>
                          )}
                        </div>
                        <div className="eval-phoenix-note">
                          Logged to{' '}
                          <a href="http://localhost:6006" target="_blank" rel="noopener noreferrer">
                            Phoenix
                          </a>
                        </div>
                      </div>
                    )}
                    {msg.evalResult?.error && (
                      <div className="chat-eval-result">
                        <span className="eval-error">Eval failed</span>
                        <div className="eval-phoenix-note">
                          Check{' '}
                          <a href="http://localhost:6006" target="_blank" rel="noopener noreferrer">
                            Phoenix
                          </a>
                          {' '}for details
                        </div>
                      </div>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <div className="sources">
                        <div className="sources-label">Sources</div>
                        {msg.sources.map((src, j) => (
                          <div key={j} className="source-item">
                            <span className="source-badge">{src.doc_id}</span>
                            <span>
                              {src.section}
                              {src.subsection ? ` > ${src.subsection}` : ''}
                            </span>
                          </div>
                        ))}
                        {msg.latency_ms && (
                          <div className="latency">
                            Answered in {(msg.latency_ms / 1000).toFixed(1)}s
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
                {!loading && messages.length > 0 && getFilteredSuggestions().length > 0 && (
                  <div className="follow-up-suggestions">
                    <div className="follow-up-label">Ask another question</div>
                    <div className="suggestions">
                      {getFilteredSuggestions().map((q, i) => (
                        <button
                          key={i}
                          className="suggestion-chip"
                          onClick={() => sendQuestion(q)}
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {loading && (
                  <div className="message assistant">
                    <div className="message-label">Policy Assistant</div>
                    <div className="message-bubble">
                      <div className="loading-dots">
                        <span></span>
                        <span></span>
                        <span></span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="input-area">
            <form className="input-form" onSubmit={handleSubmit}>
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask a policy question..."
                disabled={loading}
              />
              <button
                type="submit"
                className="send-btn"
                disabled={!input.trim() || loading}
              >
                Send
              </button>
            </form>
          </div>
        </>
      ) : (
        <div className="eval-container">
          <EvalDashboard />
        </div>
      )}
    </div>
  )
}

export default App
