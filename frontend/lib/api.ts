const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
}

class ApiClient {
  private getHeaders(customHeaders: Record<string, string> = {}): Record<string, string> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...customHeaders,
    };

    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const activeWorkspaceId = localStorage.getItem("active_workspace_id");
      if (activeWorkspaceId) {
        headers["X-Workspace-ID"] = activeWorkspaceId;
      }
    }

    return headers;
  }

  async request<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

    const headers = this.getHeaders(
      (options.headers as Record<string, string>) || {}
    );

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        return {
          success: false,
          error: data?.error || {
            code: `HTTP_${response.status}`,
            message: data?.detail || response.statusText || "Request failed",
          },
        };
      }

      return data;
    } catch (err: any) {
      return {
        success: false,
        error: {
          code: "NETWORK_ERROR",
          message: err.message || "Network error. Please check your connection.",
        },
      };
    }
  }

  get<T = any>(endpoint: string, headers?: Record<string, string>) {
    return this.request<T>(endpoint, { method: "GET", headers });
  }

  post<T = any>(endpoint: string, body?: any, headers?: Record<string, string>) {
    return this.request<T>(endpoint, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  patch<T = any>(endpoint: string, body?: any, headers?: Record<string, string>) {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
      headers,
    });
  }

  delete<T = any>(endpoint: string, headers?: Record<string, string>) {
    return this.request<T>(endpoint, { method: "DELETE", headers });
  }

  async uploadFormData<T = any>(endpoint: string, formData: FormData): Promise<ApiResponse<T>> {
    const url = endpoint.startsWith("http")
      ? endpoint
      : `${API_BASE_URL}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

    const headers: Record<string, string> = {};
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) headers["Authorization"] = `Bearer ${token}`;
      const activeWorkspaceId = localStorage.getItem("active_workspace_id");
      if (activeWorkspaceId) headers["X-Workspace-ID"] = activeWorkspaceId;
    }

    try {
      const response = await fetch(url, {
        method: "POST",
        body: formData,
        headers,
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) {
        return {
          success: false,
          error: data?.error || {
            code: `HTTP_${response.status}`,
            message: data?.detail || response.statusText || "Upload failed",
          },
        };
      }
      return data;
    } catch (err: any) {
      return {
        success: false,
        error: {
          code: "NETWORK_ERROR",
          message: err.message || "Network error. Please check your connection.",
        },
      };
    }
  }

  async streamChat(
    conversationId: string,
    content: string,
    callbacks: {
      onCitations?: (citations: any[]) => void;
      onToken?: (token: string) => void;
      onDone?: (data: { message_id: string }) => void;
      onError?: (error: any) => void;
    }
  ): Promise<void> {
    const url = `${API_BASE_URL}/chat/conversations/${conversationId}/messages`;
    const headers = this.getHeaders();

    try {
      const response = await fetch(url, {
        method: "POST",
        headers,
        body: JSON.stringify({ content, stream: true }),
      });

      if (!response.ok || !response.body) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || response.statusText || "Streaming request failed");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const block of lines) {
          if (!block.trim()) continue;
          const blockLines = block.split("\n");
          let currentEvent = "";
          let dataStr = "";

          for (const line of blockLines) {
            if (line.startsWith("event: ")) {
              currentEvent = line.replace("event: ", "").trim();
            } else if (line.startsWith("data: ")) {
              dataStr = line.replace("data: ", "").trim();
            }
          }

          if (dataStr) {
            try {
              const parsedData = JSON.parse(dataStr);
              if (currentEvent === "citations" && callbacks.onCitations) {
                callbacks.onCitations(parsedData);
              } else if (currentEvent === "token" && callbacks.onToken) {
                callbacks.onToken(parsedData.token || "");
              } else if (currentEvent === "done" && callbacks.onDone) {
                callbacks.onDone(parsedData);
              }
            } catch (e) {
              console.error("Failed to parse SSE event payload", e);
            }
          }
        }
      }
    } catch (err: any) {
      if (callbacks.onError) {
        callbacks.onError(err);
      } else {
        throw err;
      }
    }
  }
}

export const api = new ApiClient();

