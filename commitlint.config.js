// commitlint configuration
// See: https://commitlint.js.org/

module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Type rules
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature
        'fix',      // Bug fix
        'docs',     // Documentation only changes
        'style',    // Code style changes (formatting, semicolons, etc.)
        'refactor', // Code change that neither fixes a bug nor adds a feature
        'perf',     // Performance improvement
        'test',     // Adding missing tests or correcting existing tests
        'build',    // Changes that affect the build system or external dependencies
        'ci',       // Changes to CI configuration files and scripts
        'chore',    // Other changes that don't modify src or test files
        'revert',   // Reverts a previous commit
      ],
    ],
    
    // Scope rules
    'scope-case': [2, 'always', 'lower-case'],
    'scope-empty': [1, 'never'], // Warn if no scope
    
    // Subject rules
    'subject-case': [2, 'never', ['start-case', 'pascal-case', 'upper-case']],
    'subject-empty': [2, 'never'], // Subject required
    'subject-full-stop': [2, 'never', '.'],
    'subject-max-length': [2, 'always', 72],
    
    // Header rules
    'header-max-length': [2, 'always', 100],
    
    // Body rules
    'body-leading-blank': [1, 'always'],
    'body-max-line-length': [2, 'always', 120],
    
    // Footer rules
    'footer-leading-blank': [1, 'always'],
    'footer-max-line-length': [2, 'always', 120],
    
    // Custom scopes for this project
    'scope-enum': [
      1, // Warn (not error) for unknown scopes
      'always',
      [
        // Modules
        'identity',
        'users',
        'reports',
        'cases',
        'media',
        'verification',
        'resolution',
        'departments',
        'geography',
        'analytics',
        'search',
        'ai',
        'intelligence',
        'moderation',
        'community',
        'notifications',
        'audit',
        'government',
        'data-trust',
        'communication',
        
        // Infrastructure
        'api',
        'web',
        'worker',
        'docker',
        'terraform',
        'ci',
        'deps',
        
        // General
        'security',
        'i18n',
        'docs',
        'config',
        'scripts',
        'tests',
        'migrations',
      ],
    ],
  },
  plugins: [
    {
      rules: {
        // Custom rule: require scope for certain types
        'scope-required-for-type': ({ scope, type }) => {
          const typesRequiringScope = ['feat', 'fix', 'refactor', 'perf'];
          if (typesRequiringScope.includes(type) && !scope) {
            return [
              false,
              `Scope is required for type "${type}". Use: ${type}(scope): message`,
            ];
          }
          return [true];
        },
      },
    },
  ],
  rules: {
    ...module.exports.rules,
    'scope-required-for-type': [2, 'always'],
  },
};
