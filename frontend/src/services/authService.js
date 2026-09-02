export class AuthServiceUnavailableError extends Error {
  constructor() {
    super('ScholarZone authentication is not connected yet.')
    this.name = 'AuthServiceUnavailableError'
  }
}

// Replace these methods with the FastAPI adapter when the authentication API exists.
// This module deliberately does not persist credentials, tokens, or user data.
export const authService = {
  async checkSession() {
    return null
  },

  async login() {
    throw new AuthServiceUnavailableError()
  },

  async register() {
    throw new AuthServiceUnavailableError()
  },

  async logout() {
    return null
  },
}
