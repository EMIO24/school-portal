var mockAxiosInstance;
var mockRequestInterceptor;
var mockResponseSuccessInterceptor;
var mockResponseErrorInterceptor;

jest.mock("axios", () => {
  mockAxiosInstance = {
    defaults: { headers: { "Content-Type": "application/json" }, timeout: 15000 },
    interceptors: {
      request: { use: jest.fn((onFulfilled) => { mockRequestInterceptor = onFulfilled; }) },
      response: { use: jest.fn((onFulfilled, onRejected) => {
        mockResponseSuccessInterceptor = onFulfilled;
        mockResponseErrorInterceptor = onRejected;
      }) },
    },
  };
  return {
    __esModule: true,
    default: { create: jest.fn(() => mockAxiosInstance), post: jest.fn() },
  };
});

import axios from "axios";
import { api, tokenStore } from "../../services/api";

const requestInterceptor = () => mockRequestInterceptor;
const responseSuccessInterceptor = () => mockResponseSuccessInterceptor;
const responseErrorInterceptor = () => mockResponseErrorInterceptor;

describe("API service", () => {
  beforeEach(() => {
    axios.post.mockClear();
    tokenStore.clearAll();
  });

  it("stores access tokens in memory and refresh tokens in local storage", () => {
    tokenStore.setTokens({ access: "access-token", refresh: "refresh-token" });

    expect(tokenStore.getAccess()).toBe("access-token");
    expect(tokenStore.getRefresh()).toBe("refresh-token");
    tokenStore.clearAll();
    expect(tokenStore.getAccess()).toBeNull();
    expect(tokenStore.getRefresh()).toBeNull();
  });

  it("configures the Axios instance with JSON headers and a request timeout", () => {
    expect(api.defaults.headers["Content-Type"]).toBe("application/json");
    expect(api.defaults.timeout).toBe(15000);
  });

  it("adds the current access token to outgoing request headers", () => {
    tokenStore.setAccess("access-token");
    const config = requestInterceptor()({ headers: {} });

    expect(config.headers.Authorization).toBe("Bearer access-token");
  });

  it("passes successful responses through unchanged", () => {
    const response = { status: 200, data: { ok: true } };

    expect(responseSuccessInterceptor()(response)).toBe(response);
  });

  it("rejects non-authentication errors without attempting a token refresh", async () => {
    const error = { response: { status: 500 }, config: { headers: {} } };

    await expect(responseErrorInterceptor()(error)).rejects.toBe(error);
    expect(axios.post).not.toHaveBeenCalled();
  });
});
