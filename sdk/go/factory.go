package hardenhmac

import (
	"io"
	"net/http"
	"strings"
)

// ClientFactory creates pre-configured HTTP clients for named targets.
type ClientFactory struct {
	config *HmacConfig
}

// NewClientFactory creates a new factory from the given configuration.
func NewClientFactory(config *HmacConfig) *ClientFactory {
	return &ClientFactory{config: config}
}

// CreateClient returns a Client pre-configured with the target's base URL and automatic HMAC signing.
// The target name is sent as X-Harden-Client-Id.
func (f *ClientFactory) CreateClient(targetName string) (*Client, error) {
	target, ok := f.config.Targets[targetName]
	if !ok {
		available := make([]string, 0, len(f.config.Targets))
		for k := range f.config.Targets {
			available = append(available, k)
		}
		return nil, &ConfigError{
			Message: "Target '" + targetName + "' is not configured. Available targets: " + formatList(available) + ".",
		}
	}

	effectiveConfig, err := f.config.ForTarget(targetName)
	if err != nil {
		return nil, err
	}

	transport := &SigningTransport{
		Config:     effectiveConfig,
		TargetName: targetName,
		Base:       http.DefaultTransport,
	}

	return &Client{
		Client:  &http.Client{Transport: transport},
		BaseURL: strings.TrimRight(target.BaseURL, "/"),
	}, nil
}

// Client wraps http.Client with a base URL for convenience methods.
type Client struct {
	*http.Client
	// BaseURL is the base URL for the target service (no trailing slash).
	BaseURL string
}

// Get makes a signed GET request to BaseURL + path.
func (c *Client) Get(path string) (*http.Response, error) {
	url := c.BaseURL + path
	return c.Client.Get(url)
}

// Post makes a signed POST request to BaseURL + path.
func (c *Client) Post(path string, contentType string, body string) (*http.Response, error) {
	url := c.BaseURL + path
	return c.Client.Post(url, contentType, strings.NewReader(body))
}

// Do sends an HTTP request using the underlying signed client.
// The request URL must be absolute. Use NewRequest to build a request with BaseURL prepended.
func (c *Client) Do(req *http.Request) (*http.Response, error) {
	return c.Client.Do(req)
}

// NewRequest creates a new http.Request with the base URL prepended to the path.
func (c *Client) NewRequest(method, path string, body io.Reader) (*http.Request, error) {
	url := c.BaseURL + path
	return http.NewRequest(method, url, body)
}
