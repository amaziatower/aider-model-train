﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// IMiddleware.cs

using System.Threading;
using System.Threading.Tasks;

namespace AutoGen.Core.Middleware;

/// <summary>
/// The middleware interface
/// </summary>
public interface IMiddleware
{
    /// <summary>
    /// the name of the middleware
    /// </summary>
    public string? Name { get; }

    /// <summary>
    /// The method to invoke the middleware
    /// </summary>
    public Task<Message> InvokeAsync(
        MiddlewareContext context,
        IAgent agent,
        CancellationToken cancellationToken = default);
}
