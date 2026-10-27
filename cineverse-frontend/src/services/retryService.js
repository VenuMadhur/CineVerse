import { apiClient } from './apiClient';

const retryService = {
  /**
   * Fetches all retry configurations.
   * @param {number} skip - Offset for pagination.
   * @param {number} limit - Maximum number of records to return.
   * @returns {Promise<Object>} The paginated response with items array.
   */
  async getConfigurations(skip = 0, limit = 100) {
    const response = await apiClient.get('/retry/configuration', {
      params: { skip, limit },
    });
    return response.data;
  },

  /**
   * Fetches a single retry configuration by ID.
   * @param {string} id - The UUID of the configuration.
   * @returns {Promise<Object>} The retry configuration.
   */
  async getConfiguration(id) {
    const response = await apiClient.get(`/retry/configuration/${id}`);
    return response.data;
  },

  /**
   * Creates a new retry configuration.
   * @param {Object} data - Contains retry_attempt and retry_after_days.
   * @returns {Promise<Object>} The created retry configuration.
   */
  async createConfiguration(data) {
    const response = await apiClient.post('/retry/configuration', data);
    return response.data;
  },

  /**
   * Updates an existing retry configuration.
   * @param {string} id - The UUID of the configuration.
   * @param {Object} data - Optional fields to update (retry_after_days, is_active).
   * @returns {Promise<Object>} The updated retry configuration.
   */
  async updateConfiguration(id, data) {
    const response = await apiClient.patch(`/retry/configuration/${id}`, data);
    return response.data;
  },
};

export default retryService;
