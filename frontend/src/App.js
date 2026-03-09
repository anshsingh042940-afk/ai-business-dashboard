import { useState, useRef, useEffect } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar, Line, Pie, Doughnut } from "react-chartjs-2";
import "./App.css";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

const API_URL = "http://localhost:8001";

function App() {
  const [query, setQuery] = useState("");
  const [chartData, setChartData] = useState(null);
  const [chartType, setChartType] = useState("bar");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [uploadStatus, setUploadStatus] = useState("");
  const [aiConclusion, setAiConclusion] = useState(null);
  const [tableColumns, setTableColumns] = useState([]);
  const fileInputRef = useRef(null);

  // Fetch table columns on mount
  useEffect(() => {
    fetchTableColumns();
  }, []);

  const fetchTableColumns = async () => {
    try {
      const response = await fetch(`${API_URL}/table-info`);
      if (response.ok) {
        const data = await response.json();
        setTableColumns(data.columns || []);
      }
    } catch (err) {
      console.error("Failed to fetch table columns:", err);
    }
  };

  const handleQuery = async () => {
    if (!query.trim()) return;
    
    setLoading(true);
    setError(null);
    setChartData(null);
    setAiConclusion(null);
    
    try {
      const response = await fetch(`${API_URL}/query`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query }),
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.error) {
        setError(result.error);
      } else if (!result.labels || !result.data || result.data.length === 0) {
        setError("No data returned from query. Please try a different query.");
      } else {
        setChartData(result);
        setChartType(result.chartType || "bar");
        
        setChatHistory(prev => [...prev, {
          query: query,
          result: result,
          timestamp: new Date().toISOString()
        }]);
        
        // Fetch AI conclusion
        try {
          const conclusionResponse = await fetch(`${API_URL}/conclusion`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ query }),
          });
          
          if (conclusionResponse.ok) {
            const conclusionData = await conclusionResponse.json();
            setAiConclusion(conclusionData);
          }
        } catch (conclusionErr) {
          console.error("Failed to get conclusion:", conclusionErr);
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    setLoading(true);
    setUploadStatus("Uploading...");
    
    try {
      const formData = new FormData();
      formData.append("file", file);
      
      const response = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });
      
      if (!response.ok) {
        throw new Error("Failed to upload file");
      }
      
      const result = await response.json();
      setUploadStatus(`Successfully uploaded: ${result.filename}`);
      
      // Fetch updated table columns
      await fetchTableColumns();
      
      setChartData(null);
      setChatHistory([]);
      
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleQuery();
    }
  };

  const handleSuggestionClick = (suggestion) => {
    setQuery(suggestion);
  };

  const getChartComponent = () => {
    if (!chartData) return null;

    const data = {
      labels: chartData.labels,
      datasets: [
        {
          label: chartData.title || "Data",
          data: chartData.data,
          backgroundColor: [
            "rgba(74, 144, 217, 0.7)",
            "rgba(80, 227, 194, 0.7)",
            "rgba(255, 99, 132, 0.7)",
            "rgba(255, 206, 86, 0.7)",
            "rgba(153, 102, 255, 0.7)",
            "rgba(255, 159, 64, 0.7)",
            "rgba(199, 199, 199, 0.7)",
            "rgba(83, 102, 255, 0.7)",
            "rgba(40, 159, 64, 0.7)",
            "rgba(210, 99, 132, 0.7)",
          ],
          borderColor: [
            "rgba(74, 144, 217, 1)",
            "rgba(80, 227, 194, 1)",
            "rgba(255, 99, 132, 1)",
            "rgba(255, 206, 86, 1)",
            "rgba(153, 102, 255, 1)",
            "rgba(255, 159, 64, 1)",
            "rgba(199, 199, 199, 1)",
            "rgba(83, 102, 255, 1)",
            "rgba(40, 159, 64, 1)",
            "rgba(210, 99, 132, 1)",
          ],
          borderWidth: 2,
          borderRadius: 4,
        },
      ],
    };

    const options = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "top",
          labels: {
            usePointStyle: true,
            padding: 20,
            font: {
              size: 13,
            },
          },
        },
        title: {
          display: true,
          text: chartData.title || "Chart",
          font: {
            size: 18,
            weight: "600",
          },
          padding: {
            bottom: 20,
          },
        },
      },
      scales: {
        x: {
          grid: {
            display: false,
          },
        },
        y: {
          grid: {
            color: "rgba(0, 0, 0, 0.05)",
          },
        },
      },
    };

    switch (chartType) {
      case "line":
        return <Line data={data} options={options} />;
      case "pie":
        return <Pie data={data} options={options} />;
      case "doughnut":
        return <Doughnut data={data} options={options} />;
      case "bar":
      default:
        return <Bar data={data} options={options} />;
    }
  };

  const getSuggestedQueries = () => {
    if (tableColumns.length === 0) {
      return [
        "Show claims paid by company",
        "Show claims paid by year",
        "Show total claims intimated by insurer",
        "Show average claims paid ratio by year",
        "Show claims repudiated by company",
      ];
    }
    
    // Find column types
    const hasYear = tableColumns.some(col => col.toLowerCase().includes('year') || col.toLowerCase().includes('date'));
    const hasName = tableColumns.some(col => col.toLowerCase().includes('name') || col.toLowerCase().includes('company') || col.toLowerCase().includes('insurer'));
    const hasAmount = tableColumns.some(col => col.toLowerCase().includes('amount') || col.toLowerCase().includes('revenue') || col.toLowerCase().includes('sales'));
    const hasCount = tableColumns.some(col => col.toLowerCase().includes('count') || col.toLowerCase().includes('no') || col.toLowerCase().includes('quantity'));
    
    const queries = [];
    if (hasName && hasAmount) queries.push(`Show total by name`);
    if (hasYear && hasAmount) queries.push(`Show by year`);
    if (hasName && hasCount) queries.push(`Show count by name`);
    if (hasYear && hasCount) queries.push(`Show count by year`);
    
    // Add default queries if not enough
    if (queries.length < 3) {
      queries.push("Show all data", "Show summary");
    }
    
    return queries.slice(0, 5);
  };

  return (
    <div className="app-container">
      <div className="header">
        <h1 className="title">AI Business Dashboard</h1>
        <p className="subtitle">
          Ask questions in natural language and get instant visualizations
        </p>
      </div>

      {/* File Upload Section */}
      <div className="card upload-section">
        <div className="upload-wrapper">
          <label className="upload-label">Upload CSV Dataset:</label>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="file-input"
            disabled={loading}
          />
        </div>
        {uploadStatus && (
          <div className={uploadStatus.includes("Successfully") ? "upload-success" : "upload-error"}>
            {uploadStatus}
          </div>
        )}
      </div>

      <div className="input-section">
        <div className="input-wrapper">
          <input
            className="query-input"
            placeholder="Ask a business question (e.g., 'Show claims paid by company')"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
          />
          <button
            className="generate-btn"
            onClick={handleQuery}
            disabled={loading}
          >
            {loading ? "Loading..." : "Generate Dashboard"}
          </button>
        </div>
      </div>

      <div className="suggestions">
        <p className="suggestion-label">Try these queries:</p>
        <div className="suggestion-buttons">
          {getSuggestedQueries().map((suggestion, index) => (
            <button
              key={index}
              className="suggestion-btn"
              onClick={() => handleSuggestionClick(suggestion)}
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="error-message">
          Error: {error}
        </div>
      )}

      {loading && (
        <div className="loading-container">
          <div className="spinner"></div>
          <p className="loading-text">Loading data...</p>
        </div>
      )}

      {chartData && !loading && (
        <div className="chart-container">
          <div className="chart-wrapper">
            {getChartComponent()}
          </div>
          <div className="chart-info">
            <p><strong>Chart Type:</strong> {chartType}</p>
            <p><strong>Data Points:</strong> {chartData.labels?.length || 0}</p>
          </div>
        </div>
      )}

      {/* AI Conclusion Section */}
      {aiConclusion && !loading && (
        <div className="card conclusion-section">
          <h3 className="conclusion-title">AI Business Conclusion</h3>
          <div className="conclusion-content">
            <p className="conclusion-text">{aiConclusion.conclusion}</p>
            {aiConclusion.analysis && (
              <div className="conclusion-stats">
                <div className="stat-item">
                  <span className="stat-label">Highest:</span>
                  <span className="stat-value">{aiConclusion.analysis.highest?.label} ({aiConclusion.analysis.highest?.value?.toLocaleString()})</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Lowest:</span>
                  <span className="stat-value">{aiConclusion.analysis.lowest?.label} ({aiConclusion.analysis.lowest?.value?.toLocaleString()})</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Average:</span>
                  <span className="stat-value">{aiConclusion.analysis.average?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Total:</span>
                  <span className="stat-value">{aiConclusion.analysis.total?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chat History Section */}
      {chatHistory.length > 0 && (
        <div className="card history-section">
          <h3 className="history-title">Query History</h3>
          <div className="history-list">
            {chatHistory.map((item, index) => (
              <div key={index} className="history-item">
                <p className="history-query"><strong>Q:</strong> {item.query}</p>
                <p className="history-result">
                  <strong>Result:</strong> {item.result.data?.length || 0} data points
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!chartData && !loading && !error && (
        <div className="placeholder">
          <p>Enter a query above to generate a chart</p>
          <p>Or upload your own CSV dataset above</p>
        </div>
      )}
    </div>
  );
}

export default App;

